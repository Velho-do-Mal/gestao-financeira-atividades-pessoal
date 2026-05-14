"""
pages/atividades.py
Gestão de Tarefas, Plano de Ação (5W2H) e Pomodoro — BK Finanças

CORREÇÕES v2:
  1. cache limpo antes de st.rerun() → atividade aparece imediatamente após salvar
  2. Botão ✏️ Editar por atividade com formulário inline
  3. Descrição exibida abaixo do título na listagem
  4. st.toast() substitui st.success() → confirmação persiste durante rerun
  5. Selectbox de status limpa cache antes de rerun → sem loop de re-save
  6. 5W2H: botão de excluir por linha (substitui campo de ID manual)
  7. get_activities() chamado uma única vez por render
  8. Hierarquia recursiva: sub-sub-atividades agora renderizadas
  9. description NaN tratado antes de salvar
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import time

from database.queries import (
    get_activities, upsert_activity, delete_activity,
    get_action_plans, upsert_action_plan, delete_action_plan,
    clear_data_cache,
)
from components.styles import page_header
from utils.helpers import priority_emoji, status_icon, fmt_date

PRIORITIES = [
    "Urgente-Urgente",
    "Importante-Urgente",
    "Importante não Urgente",
    "Não importante-Não urgente",
]
STATUS_LIST = ["Não iniciado", "Em andamento", "Concluído"]


def render():
    page_header("Atividades", "Gestão de Tarefas, Ações e Produtividade", "📋")
    tabs = st.tabs(["📋 Atividades", "🗂️ Plano de Ação (5W2H)", "🍅 Pomodoro"])
    with tabs[0]: _tab_atividades()
    with tabs[1]: _tab_plano_acao()
    with tabs[2]: _tab_pomodoro()


# ══════════════════════════════════════════════════════════════════
# HELPERS DE SESSÃO
# ══════════════════════════════════════════════════════════════════

def _get_editing_id():
    return st.session_state.get('_edit_act_id')

def _set_editing_id(act_id):
    st.session_state['_edit_act_id'] = act_id

def _save_and_reload():
    """Limpa cache e recarrega — BUG 1 FIX."""
    clear_data_cache()
    st.rerun()


# ══════════════════════════════════════════════════════════════════
# ABA 1 — ATIVIDADES
# ══════════════════════════════════════════════════════════════════

def _tab_atividades():
    st.markdown("### 📋 Gerenciamento de Atividades")

    # BUG 7 FIX: get_activities() chamado UMA VEZ e reaproveitado
    df_all = get_activities()

    # key muda ao salvar → expander reseta para expanded=False (fecha automaticamente)
    with st.expander("➕ Nova Atividade", expanded=False,
                     key=f"exp_new_act_{st.session_state.get('_act_form_key', 0)}"):
        _form_nova_atividade(df_all)

    if df_all.empty:
        st.info("Nenhuma atividade cadastrada. Crie sua primeira atividade acima!")
        return

    # Filtros
    cf1, cf2, cf3 = st.columns(3)
    f_priority = cf1.selectbox("Filtrar Prioridade", ["Todas"] + PRIORITIES, key="f_prior")
    f_status   = cf2.selectbox("Filtrar Status",    ["Todos"]  + STATUS_LIST, key="f_stat")
    f_search   = cf3.text_input("Buscar", placeholder="Título...", key="f_search")

    df_filtered = df_all.copy()
    if f_priority != "Todas":
        df_filtered = df_filtered[df_filtered['priority'] == f_priority]
    if f_status != "Todos":
        df_filtered = df_filtered[df_filtered['status'] == f_status]
    if f_search:
        df_filtered = df_filtered[
            df_filtered['title'].str.contains(f_search, case=False, na=False)
        ]

    n_main = len(df_filtered[df_filtered['parent_id'].isna()])
    st.markdown(f"**{n_main} atividade(s) encontrada(s)**")
    st.markdown("---")

    # Passa df_all para _render_children encontrar filhos mesmo que filtrados
    _render_activity_tree(df_filtered, df_all)


def _form_nova_atividade(df_all: pd.DataFrame):
    """Formulário sem st.form para reset limpo após salvar."""
    if '_new_act_key' not in st.session_state:
        st.session_state['_new_act_key'] = 0
    k = st.session_state['_new_act_key']

    parent_options = {"— Nenhuma (atividade principal) —": None}
    if not df_all.empty:
        main = df_all[df_all['parent_id'].isna()]
        parent_options.update({r['title']: r['id'] for _, r in main.iterrows()})

    title       = st.text_input("Título da Atividade*",         key=f"na_tit_{k}")
    description = st.text_area("Descrição", height=60,          key=f"na_dsc_{k}")
    parent_sel  = st.selectbox("Atividade Pai (subatividade?)",
                                list(parent_options.keys()),    key=f"na_par_{k}")
    parent_id   = parent_options.get(parent_sel)

    c1, c2, c3, c4 = st.columns(4)
    start_date = c1.date_input("Início",    value=date.today(),                    key=f"na_sd_{k}")
    end_date   = c2.date_input("Conclusão", value=date.today() + timedelta(days=7), key=f"na_ed_{k}")
    priority   = c3.selectbox("Prioridade", PRIORITIES, index=2,                   key=f"na_pr_{k}")
    status     = c4.selectbox("Status",     STATUS_LIST,                            key=f"na_st_{k}")

    if st.button("💾 Salvar Atividade", key=f"na_btn_{k}",
                 type="primary", use_container_width=True):
        if title.strip():
            upsert_activity(dict(
                title=title.strip(),
                description=description.strip() or None,  # BUG 9 FIX: sem NaN
                parent_id=parent_id,
                start_date=start_date,
                end_date=end_date,
                priority=priority,
                status=status,
            ))
            st.toast("✅ Atividade salva!", icon="✅")  # BUG 4 FIX
            st.session_state['_new_act_key'] += 1
            # Incrementa chave do expander → ele fecha automaticamente após rerun
            st.session_state['_act_form_key'] = st.session_state.get('_act_form_key', 0) + 1
            _save_and_reload()  # BUG 1 FIX
        else:
            st.error("Título é obrigatório.")


# ══════════════════════════════════════════════════════════════════
# RENDERIZAÇÃO HIERÁRQUICA RECURSIVA
# ══════════════════════════════════════════════════════════════════

def _render_activity_tree(df_filtered: pd.DataFrame, df_all: pd.DataFrame):
    """
    df_filtered: atividades que passam nos filtros (usada para mães visíveis)
    df_all:      TODAS as atividades (usada para encontrar filhos)

    Separação necessária: se filho tem prioridade/status fora do filtro ativo,
    ele seria removido de df_filtered e nunca apareceria — mesmo salvo no banco.
    """
    today     = date.today()
    main_acts = df_filtered[df_filtered['parent_id'].isna()]
    for _, act in main_acts.iterrows():
        _render_activity_row(act, today, depth=0)
        _render_children(df_all, int(act['id']), today, depth=1)


def _render_children(df: pd.DataFrame, parent_id: int,
                     today: date, depth: int, max_depth: int = 5):
    """
    Renderiza filhos de uma atividade recursivamente.
    Usa apply() para comparação robusta de parent_id — indiferente ao
    dtype pandas (object, float64, Int64, numpy.int64).
    """
    if depth > max_depth:
        return

    def _matches(val) -> bool:
        """True se val representa o mesmo inteiro que parent_id."""
        if val is None:
            return False
        try:
            if isinstance(val, float) and pd.isna(val):
                return False
            return int(val) == int(parent_id)
        except (ValueError, TypeError):
            return False

    children = df[df['parent_id'].apply(_matches)]
    for _, child in children.iterrows():
        _render_activity_row(child, today, depth=depth)
        _render_children(df, int(child['id']), today, depth + 1, max_depth)


# ══════════════════════════════════════════════════════════════════
# LINHA DE ATIVIDADE
# ══════════════════════════════════════════════════════════════════

def _render_activity_row(row, today: date, depth: int = 0):
    act_id     = int(row['id'])
    is_editing = _get_editing_id() == act_id
    if is_editing:
        _render_edit_form(row, depth=depth)
    else:
        _render_view_row(row, today, depth)


def _render_view_row(row, today: date, depth: int = 0):
    act_id = int(row['id'])
    is_sub = depth > 0

    end_d = row.get('end_date')
    if end_d and not isinstance(end_d, date):
        try:    end_d = pd.to_datetime(end_d).date()
        except: end_d = None

    icon    = status_icon(row.get('status', ''), end_d)
    p_emoji = priority_emoji(row.get('priority', ''))

    desc = str(row.get('description') or '').strip()
    desc_html = (
        f'<div style="font-size:12px;color:#94A3B8;margin-top:3px;'
        f'padding-left:6px;border-left:2px solid #334155">{desc}</div>'
        if desc else ''
    )

    # ── Colunas com indentação integrada ──────────────────────────
    # Para subatividades: primeira coluna é um espaçador visual
    # O espaçador fica DENTRO do grid → row inteira fica deslocada visualmente
    if is_sub:
        indent_w = min(depth * 0.6, 1.8)   # largura do espaçador
        info_w   = max(5.0 - indent_w, 2.5)
        all_cols = st.columns([indent_w, info_w, 2, 2, 1, 1])
        # Espaçador: linha vertical azul indicando hierarquia
        with all_cols[0]:
            st.markdown(
                f'<div style="border-left:3px solid #3B82F6;height:54px;'
                f'margin-left:{(depth-1)*8}px;margin-top:4px"></div>',
                unsafe_allow_html=True,
            )
        col_info, col_status, col_dates, col_edit, col_del = (
            all_cols[1], all_cols[2], all_cols[3], all_cols[4], all_cols[5]
        )
    else:
        col_info, col_status, col_dates, col_edit, col_del = st.columns([5, 2, 2, 1, 1])

    with col_info:
        fw    = '500' if is_sub else '700'
        color = '#CBD5E1' if is_sub else '#F1F5F9'
        st.markdown(f"""
        <div style="padding:6px 0">
            <span style="font-weight:{fw};color:{color}">{icon} {p_emoji} {row['title']}</span>
            <br>
            <span style="font-size:11px;color:#64748B">{row.get('priority','')}</span>
            {desc_html}
        </div>
        """, unsafe_allow_html=True)

    with col_status:
        cur_status = row.get('status', 'Não iniciado')
        try:    idx = STATUS_LIST.index(cur_status)
        except: idx = 0
        new_status = st.selectbox(
            "", STATUS_LIST, index=idx,
            key=f"stat_{act_id}", label_visibility="collapsed",
        )
        # BUG 5 FIX: limpa cache para evitar loop de re-save
        if new_status != cur_status:
            upsert_activity(dict(
                id=act_id,
                title=row['title'],
                status=new_status,
                priority=row.get('priority'),
                start_date=row.get('start_date'),
                end_date=row.get('end_date'),
                parent_id=row.get('parent_id'),
                description=str(row.get('description') or '').strip() or None,
            ))
            st.toast(f"Status → {new_status}", icon="✅")
            _save_and_reload()

    with col_dates:
        overdue = end_d and end_d < today and row.get('status') != 'Concluído'
        color   = "#EF4444" if overdue else "#94A3B8"
        st.markdown(f"""
        <div style="font-size:12px;color:{color};padding:8px 0">
            📅 {fmt_date(row.get('start_date'))} → {fmt_date(end_d)}
        </div>
        """, unsafe_allow_html=True)

    # BUG 2 FIX: botão de editar
    with col_edit:
        if st.button("✏️", key=f"edit_act_{act_id}", help="Editar atividade"):
            _set_editing_id(act_id)
            st.rerun()

    with col_del:
        if st.button("🗑️", key=f"del_act_{act_id}", help="Excluir atividade"):
            delete_activity(act_id)
            st.toast("🗑️ Atividade excluída.", icon="🗑️")
            _save_and_reload()


def _render_edit_form(row, depth: int = 0):
    """BUG 2 FIX: formulário de edição inline por atividade."""
    act_id = int(row['id'])
    k      = f"edt_{act_id}"

    cur_title  = str(row.get('title', ''))
    cur_desc   = str(row.get('description') or '')
    cur_start  = row.get('start_date')
    cur_end    = row.get('end_date')
    cur_prior  = row.get('priority', PRIORITIES[2])
    cur_status = row.get('status', STATUS_LIST[0])

    for attr, default in [('cur_start', date.today()), ('cur_end', date.today())]:
        val = locals()[attr]
        if val and not isinstance(val, date):
            try:    locals()[attr] = pd.to_datetime(val).date()
            except: locals()[attr] = default

    if cur_start and not isinstance(cur_start, date):
        try:    cur_start = pd.to_datetime(cur_start).date()
        except: cur_start = date.today()
    if cur_end and not isinstance(cur_end, date):
        try:    cur_end = pd.to_datetime(cur_end).date()
        except: cur_end = date.today()

    try: prior_idx  = PRIORITIES.index(cur_prior)
    except ValueError: prior_idx = 2
    try: status_idx = STATUS_LIST.index(cur_status)
    except ValueError: status_idx = 0

    margin = depth * 28
    st.markdown(f"""
    <div style="background:#1E3A5F;border-radius:10px;padding:10px 16px;
                margin-bottom:8px;margin-left:{margin}px;border:1px solid #3B82F6">
        <span style="color:#60A5FA;font-weight:600">✏️ Editando atividade</span>
    </div>
    """, unsafe_allow_html=True)

    new_title = st.text_input("Título*",   value=cur_title, key=f"{k}_title")
    new_desc  = st.text_area("Descrição",  value=cur_desc,  key=f"{k}_desc", height=70)

    c1, c2, c3, c4 = st.columns(4)
    new_start  = c1.date_input("Início",    value=cur_start or date.today(), key=f"{k}_sd")
    new_end    = c2.date_input("Conclusão", value=cur_end   or date.today(), key=f"{k}_ed")
    new_prior  = c3.selectbox("Prioridade", PRIORITIES,  index=prior_idx,   key=f"{k}_pr")
    new_status = c4.selectbox("Status",     STATUS_LIST, index=status_idx,  key=f"{k}_st")

    cs, cc = st.columns(2)
    if cs.button("💾 Salvar edição", key=f"{k}_save", type="primary", use_container_width=True):
        if new_title.strip():
            upsert_activity(dict(
                id=act_id,
                title=new_title.strip(),
                description=new_desc.strip() or None,
                start_date=new_start,
                end_date=new_end,
                priority=new_prior,
                status=new_status,
                parent_id=row.get('parent_id'),
            ))
            _set_editing_id(None)
            st.toast("✅ Atividade atualizada!", icon="✅")
            _save_and_reload()
        else:
            st.error("Título é obrigatório.")

    if cc.button("❌ Cancelar", key=f"{k}_cancel", use_container_width=True):
        _set_editing_id(None)
        st.rerun()

    st.markdown("---")


# ══════════════════════════════════════════════════════════════════
# ABA 2 — PLANO DE AÇÃO (5W2H)
# ══════════════════════════════════════════════════════════════════

def _tab_plano_acao():
    st.markdown("### 🗂️ Plano de Ação — 5W2H")

    df_acts = get_activities()
    act_options = {"— Nenhuma —": None}
    if not df_acts.empty:
        act_options.update({r['title']: r['id'] for _, r in df_acts.iterrows()})

    with st.expander("➕ Nova Ação 5W2H", expanded=False):
        with st.form("form_5w2h", clear_on_submit=True):
            act_sel = st.selectbox("Vincular a Atividade", list(act_options.keys()))
            act_id  = act_options.get(act_sel)
            c1, c2  = st.columns(2)
            what        = c1.text_area("O quê? (What)*",  height=80)
            why         = c2.text_area("Por quê? (Why)",  height=80)
            who         = c1.text_input("Quem? (Who)")
            when_date   = c2.date_input("Quando? (When)")
            where_place = c1.text_input("Onde? (Where)")
            how         = c2.text_area("Como? (How)",     height=80)
            how_much    = st.number_input("Quanto custa? (R$)", min_value=0.0, step=0.01)
            status_5w   = st.selectbox("Status", ["Pendente","Em andamento","Concluído","Cancelado"])
            if st.form_submit_button("💾 Salvar", use_container_width=True):
                if what:
                    upsert_action_plan(dict(
                        activity_id=act_id, what=what, why=why, who=who,
                        when_date=when_date, where_place=where_place,
                        how=how, how_much=how_much, status=status_5w,
                    ))
                    st.toast("✅ Ação salva!", icon="✅")
                    clear_data_cache()
                    st.rerun()
                else:
                    st.error("'O quê?' é obrigatório.")

    df_plans = get_action_plans()
    if df_plans.empty:
        st.info("Nenhum plano de ação cadastrado.")
        return

    st.markdown(f"**{len(df_plans)} ação(ões)**")

    # BUG 6 FIX: checkbox de excluir por linha + salvar status
    cols_edit = ['id','activity_title','what','who','when_date','status','how_much']
    existing  = [c for c in cols_edit if c in df_plans.columns]
    df_show   = df_plans[existing].copy()
    df_show.insert(0, 'Excluir', False)
    if 'when_date' in df_show.columns:
        df_show['when_date'] = pd.to_datetime(df_show['when_date'], errors='coerce').dt.strftime('%d/%m/%Y')
    df_show = df_show.rename(columns={
        'activity_title':'Atividade','what':'O quê?','who':'Quem?',
        'when_date':'Quando?','status':'Status','how_much':'Custo (R$)',
    })

    edited = st.data_editor(
        df_show, use_container_width=True, hide_index=True,
        height=min(400, 60 + len(df_show)*40), key="editor_5w2h",
        column_config={
            "Excluir":    st.column_config.CheckboxColumn("🗑️", width="small"),
            "id":         st.column_config.NumberColumn("ID", disabled=True, width="small"),
            "Atividade":  st.column_config.TextColumn("Atividade",  disabled=True),
            "O quê?":     st.column_config.TextColumn("O quê?",     disabled=True),
            "Quem?":      st.column_config.TextColumn("Quem?",      disabled=True),
            "Quando?":    st.column_config.TextColumn("Quando?",    disabled=True),
            "Status":     st.column_config.SelectboxColumn("Status",
                              options=["Pendente","Em andamento","Concluído","Cancelado"]),
            "Custo (R$)": st.column_config.NumberColumn("Custo (R$)", format="R$ %.2f", disabled=True),
        },
    )

    to_delete = edited[edited['Excluir'] == True]['id'].tolist()
    c_del, c_save = st.columns(2)

    if c_del.button(f"🗑️ Excluir ({len(to_delete)})",
                    disabled=(len(to_delete) == 0), use_container_width=True):
        for rid in to_delete:
            delete_action_plan(int(rid))
        st.toast(f"🗑️ {len(to_delete)} excluída(s).", icon="🗑️")
        clear_data_cache()
        st.rerun()

    if c_save.button("💾 Salvar status", type="primary", use_container_width=True):
        for _, row in edited[edited['Excluir'] == False].iterrows():
            orig = df_plans[df_plans['id'] == row['id']]
            if not orig.empty and orig.iloc[0].get('status') != row.get('Status'):
                o = orig.iloc[0]
                upsert_action_plan(dict(
                    id=int(row['id']), activity_id=o.get('activity_id'),
                    what=o.get('what'), why=o.get('why'), who=o.get('who'),
                    when_date=o.get('when_date'), where_place=o.get('where_place'),
                    how=o.get('how'), how_much=o.get('how_much'),
                    status=row.get('Status','Pendente'),
                ))
        st.toast("✅ Status atualizado!", icon="✅")
        clear_data_cache()
        st.rerun()


# ══════════════════════════════════════════════════════════════════
# ABA 3 — POMODORO
# ══════════════════════════════════════════════════════════════════

def _tab_pomodoro():
    st.markdown("### 🍅 Timer Pomodoro")
    col_c1, col_c2 = st.columns(2)
    work_minutes  = col_c1.number_input("⏱️ Trabalho (min)", 1, 120, 25)
    break_minutes = col_c2.number_input("☕ Pausa (min)",    1,  60,  5)

    for k, v in [('pom_running',False),('pom_phase','work'),
                 ('pom_end_time',None),('pom_cycles',0)]:
        if k not in st.session_state: st.session_state[k] = v

    timer_ph = st.empty()
    cycle_ph = st.empty()

    col_b1, col_b2, col_b3 = st.columns(3)
    with col_b1:
        if st.button("⏸️ Pausar" if st.session_state.pom_running else "▶️ Iniciar",
                     use_container_width=True):
            if not st.session_state.pom_running:
                dur = work_minutes if st.session_state.pom_phase == 'work' else break_minutes
                st.session_state.pom_end_time = time.time() + dur * 60
                st.session_state.pom_running  = True
            else:
                st.session_state.pom_running = False
    with col_b2:
        if st.button("🔄 Reiniciar", use_container_width=True):
            st.session_state.update(pom_running=False, pom_phase='work', pom_end_time=None)
            st.rerun()
    with col_b3:
        if st.button("⏭️ Próxima Fase", use_container_width=True):
            st.session_state.pom_phase = 'break' if st.session_state.pom_phase == 'work' else 'work'
            if st.session_state.pom_phase == 'work': st.session_state.pom_cycles += 1
            st.session_state.update(pom_running=False, pom_end_time=None)
            st.rerun()

    phase_label = "🧠 Foco" if st.session_state.pom_phase == 'work' else "☕ Pausa"
    phase_color = "#3B82F6" if st.session_state.pom_phase == 'work' else "#10B981"

    if st.session_state.pom_running and st.session_state.pom_end_time:
        remaining = st.session_state.pom_end_time - time.time()
        if remaining <= 0:
            st.session_state.pom_running = False
            if st.session_state.pom_phase == 'work':
                st.session_state.pom_cycles += 1
                st.session_state.pom_phase   = 'break'
                st.balloons()
            else:
                st.session_state.pom_phase = 'work'
            st.rerun()
        else:
            mins, secs = int(remaining // 60), int(remaining % 60)
            timer_ph.markdown(f"""
            <div style="text-align:center;padding:30px">
                <div style="font-family:monospace;font-size:72px;font-weight:700;
                           color:{phase_color};letter-spacing:4px">{mins:02d}:{secs:02d}</div>
                <div style="color:{phase_color};font-size:20px;margin-top:8px">{phase_label}</div>
            </div>""", unsafe_allow_html=True)
            cycle_ph.markdown(f'<div style="text-align:center;color:#64748B">🍅 Ciclos: <b>{st.session_state.pom_cycles}</b></div>',
                              unsafe_allow_html=True)
            time.sleep(1); st.rerun()
    else:
        dur = work_minutes if st.session_state.pom_phase == 'work' else break_minutes
        timer_ph.markdown(f"""
        <div style="text-align:center;padding:30px">
            <div style="font-family:monospace;font-size:72px;font-weight:700;
                       color:{phase_color};letter-spacing:4px;opacity:0.6">{dur:02d}:00</div>
            <div style="color:{phase_color};font-size:20px;margin-top:8px">{phase_label}</div>
        </div>""", unsafe_allow_html=True)
        cycle_ph.markdown(f'<div style="text-align:center;color:#64748B">🍅 Ciclos: <b>{st.session_state.pom_cycles}</b></div>',
                          unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("""
    <div style="background:#1E293B;border-radius:10px;padding:16px;border:1px solid #334155">
        <h4 style="color:#93C5FD;margin:0 0 8px 0">💡 Técnica Pomodoro</h4>
        <ul style="color:#94A3B8;margin:0;padding-left:20px">
            <li>Foco total durante o tempo de trabalho</li>
            <li>Pausa curta ao final de cada ciclo</li>
            <li>A cada 4 ciclos, pausa longa de 15–30 min</li>
            <li>Elimine distrações durante os períodos de foco</li>
        </ul>
    </div>""", unsafe_allow_html=True)
