"""
pages/atividades.py
Gestão de Atividades — BK Gestão Pessoal

Abas:
  📋 Tabela     — Excel-like data_editor, edição rápida, sem formulários
  🌳 Hierarquia — Visão pai/filho com indentação visual
  🗂️ 5W2H       — Plano de ação
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime

from database.queries import (
    get_activities, upsert_activity, delete_activity,
    get_action_plans, upsert_action_plan, delete_action_plan,
    get_calendar_events, clear_data_cache,
)
from datetime import time as dtime
from dateutil.relativedelta import relativedelta
from components.styles import page_header

PRIORITIES = [
    "Urgente-Urgente",
    "Importante-Urgente",
    "Importante não Urgente",
    "Não importante-Não urgente",
]
STATUS_LIST = ["Não iniciado", "Em andamento", "Concluído"]


def _reload():
    clear_data_cache()
    st.rerun()


def _get_editing_id():
    return st.session_state.get('_edit_act_id')

def _set_editing_id(act_id):
    st.session_state['_edit_act_id'] = act_id


# ══════════════════════════════════════════════════════════════════════════════
def render():
    page_header("Atividades", "Gestão de Tarefas e Ações", "📋")

    tabs = st.tabs(["📋 Tabela", "📅 Calendário", "🌳 Hierarquia", "🗂️ Plano de Ação (5W2H)"])
    with tabs[0]: _tab_tabela()
    with tabs[1]: _tab_calendario()
    with tabs[2]: _tab_hierarquia()
    with tabs[3]: _tab_plano_acao()


# ══════════════════════════════════════════════════════════════════════════════
# ABA 1 — TABELA (EXCEL-LIKE)
# ══════════════════════════════════════════════════════════════════════════════

def _tab_tabela():
    st.markdown("### 📋 Atividades — Edição Rápida")
    st.caption("Edite qualquer célula diretamente · Marque **✅** para concluir · Adicione linhas com **+** abaixo da tabela · **💾 Salvar** para confirmar")

    df_all = get_activities()

    # ── Filtros rápidos por data ──────────────────────────────────────────────
    today = date.today()
    if '_tbl_quick' not in st.session_state:
        st.session_state['_tbl_quick'] = 'todos'

    qc1, qc2, qc3, _ = st.columns([1, 1, 1, 3])
    if qc1.button(
        "📅 Hoje",
        use_container_width=True,
        type="primary" if st.session_state['_tbl_quick'] == 'hoje' else "secondary",
        key="qf_hoje",
    ):
        st.session_state['_tbl_quick'] = (
            'todos' if st.session_state['_tbl_quick'] == 'hoje' else 'hoje'
        )
        st.rerun()

    if qc2.button(
        "📆 7 dias",
        use_container_width=True,
        type="primary" if st.session_state['_tbl_quick'] == 'semana' else "secondary",
        key="qf_semana",
    ):
        st.session_state['_tbl_quick'] = (
            'todos' if st.session_state['_tbl_quick'] == 'semana' else 'semana'
        )
        st.rerun()

    if qc3.button(
        "✖ Limpar",
        use_container_width=True,
        disabled=(st.session_state['_tbl_quick'] == 'todos'),
        key="qf_clear",
    ):
        st.session_state['_tbl_quick'] = 'todos'
        st.rerun()

    # ── Filtros normais ────────────────────────────────────────────────────────
    cf1, cf2, cf3 = st.columns(3)
    f_priority = cf1.selectbox("Prioridade", ["Todas"] + PRIORITIES, key="tbl_prior")
    f_status   = cf2.selectbox("Status",     ["Todos"]  + STATUS_LIST, key="tbl_stat")
    f_search   = cf3.text_input("Buscar título", placeholder="Filtrar...", key="tbl_search")

    # Mapa nome→id para coluna "Atividade Pai"
    parent_options = ["—"]
    parent_map     = {}     # {título: id}
    if not df_all.empty:
        for _, r in df_all.iterrows():
            parent_options.append(r['title'])
            parent_map[r['title']] = int(r['id'])

    # ── Constrói DataFrame para o editor ─────────────────────────────────────
    if df_all.empty:
        df_edit = pd.DataFrame(columns=[
            'id','done','title','description',
            'start_date','end_date','priority','parent_name','delete',
        ])
    else:
        df_work = df_all.copy()

        # Aplica filtro rápido de data
        quick = st.session_state.get('_tbl_quick', 'todos')
        if quick == 'hoje':
            df_work['_end'] = pd.to_datetime(df_work['end_date'], errors='coerce').dt.date
            df_work = df_work[df_work['_end'] == today]
        elif quick == 'semana':
            df_work['_end'] = pd.to_datetime(df_work['end_date'], errors='coerce').dt.date
            df_work = df_work[
                df_work['_end'].notna() &
                (df_work['_end'] >= today) &
                (df_work['_end'] <= today + timedelta(days=7))
            ]

        # Aplica filtros normais
        if f_priority != "Todas":
            df_work = df_work[df_work['priority'] == f_priority]
        if f_status != "Todos":
            df_work = df_work[df_work['status'] == f_status]
        if f_search:
            df_work = df_work[df_work['title'].str.contains(f_search, case=False, na=False)]

        # Monta df_edit a partir dos dados filtrados
        def _safe_date(v):
            if v is None or (isinstance(v, float) and pd.isna(v)): return None
            try:
                return pd.to_datetime(v).date()
            except Exception:
                return None

        def _parent_name(pid):
            if pid is None or (isinstance(pid, float) and pd.isna(pid)): return "—"
            try:
                row = df_all[df_all['id'] == int(pid)]
                return row.iloc[0]['title'] if not row.empty else "—"
            except Exception:
                return "—"

        df_edit = pd.DataFrame({
            'id':          df_work['id'].astype('Int64'),
            'done':        df_work['status'].apply(lambda s: s == 'Concluído'),
            'title':       df_work['title'].astype(str),
            'description': df_work['description'].fillna('').astype(str),
            'start_date':  df_work['start_date'].apply(_safe_date),
            'end_date':    df_work['end_date'].apply(_safe_date),
            'priority':    df_work['priority'].fillna('Importante não Urgente').astype(str),
            'parent_name': df_work['parent_id'].apply(_parent_name),
            'delete':      False,
        })

    # ── data_editor ───────────────────────────────────────────────────────────
    edited = st.data_editor(
        df_edit,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",           # permite adicionar e remover linhas
        key="act_table_editor",
        height=max(300, min(700, len(df_edit) * 38 + 90)),
        column_config={
            "id":          st.column_config.NumberColumn("ID", disabled=True, width="small"),
            "done":        st.column_config.CheckboxColumn("✅", width="small",
                               help="Marque para concluir a atividade"),
            "title":       st.column_config.TextColumn("Título", width="large",
                               required=True),
            "description": st.column_config.TextColumn("Descrição", width="medium"),
            "start_date":  st.column_config.DateColumn("Início",   width="small",
                               format="DD/MM/YYYY"),
            "end_date":    st.column_config.DateColumn("Conclusão", width="small",
                               format="DD/MM/YYYY"),
            "priority":    st.column_config.SelectboxColumn("Prioridade", width="medium",
                               options=PRIORITIES),
            "parent_name": st.column_config.SelectboxColumn("Atividade Pai", width="medium",
                               options=parent_options),
            "delete":      st.column_config.CheckboxColumn("🗑️", width="small",
                               help="Marque para excluir"),
        },
        column_order=["done", "title", "description",
                      "start_date", "end_date", "priority", "parent_name", "delete"],
    )

    # ── Botão salvar ──────────────────────────────────────────────────────────
    n_new = len(edited[edited['id'].isna()]) if not edited.empty else 0
    n_del = len(edited[edited.get('delete', False) == True]) if not edited.empty else 0

    col_save, col_info = st.columns([2, 3])
    if col_save.button("💾 Salvar alterações", type="primary",
                       use_container_width=True, key="tbl_save"):
        saved = deleted = inserted = 0

        for _, row in edited.iterrows():
            title = str(row.get('title', '') or '').strip()
            if not title:
                continue   # ignora linhas vazias

            # Excluir
            if row.get('delete', False):
                act_id = row.get('id')
                if act_id and not pd.isna(act_id):
                    delete_activity(int(act_id))
                    deleted += 1
                continue

            # Resolve parent_id
            pname  = str(row.get('parent_name', '') or '')
            pid    = parent_map.get(pname) if pname and pname != "—" else None

            # Monta dict
            data = dict(
                title       = title,
                description = str(row.get('description', '') or '').strip() or None,
                start_date  = row.get('start_date'),
                end_date    = row.get('end_date'),
                priority    = str(row.get('priority', 'Importante não Urgente')),
                status      = 'Concluído' if row.get('done', False) else 'Em andamento',
                parent_id   = pid,
            )

            act_id = row.get('id')
            if act_id and not pd.isna(act_id):
                data['id'] = int(act_id)
                upsert_activity(data)
                saved += 1
            else:
                upsert_activity(data)
                inserted += 1

        msgs = []
        if saved:    msgs.append(f"✅ {saved} atualizado(s)")
        if inserted: msgs.append(f"➕ {inserted} criado(s)")
        if deleted:  msgs.append(f"🗑️ {deleted} excluído(s)")

        if msgs:
            st.toast(" · ".join(msgs), icon="💾")
            _reload()
        else:
            st.info("Nenhuma alteração detectada.")

    if n_new > 0 or n_del > 0:
        parts = []
        if n_new: parts.append(f"**{n_new}** nova(s)")
        if n_del: parts.append(f"**{n_del}** para excluir")
        col_info.info(" · ".join(parts) + " — clique em Salvar para confirmar")


# ══════════════════════════════════════════════════════════════════════════════
# ABA 2 — HIERARQUIA VISUAL
# ══════════════════════════════════════════════════════════════════════════════

def _tab_hierarquia():
    st.markdown("### 🌳 Visão Hierárquica")
    st.caption("Edite pela aba **📋 Tabela** · Aqui você vê a estrutura pai/filho com indentação")

    df_all = get_activities()
    if df_all.empty:
        st.info("Nenhuma atividade. Adicione pela aba **📋 Tabela**.")
        return

    # Filtros
    cf1, cf2, cf3 = st.columns(3)
    f_priority = cf1.selectbox("Prioridade", ["Todas"] + PRIORITIES, key="h_prior")
    f_status   = cf2.selectbox("Status",     ["Todos"]  + STATUS_LIST, key="h_stat")
    f_search   = cf3.text_input("Buscar",     placeholder="Título...",  key="h_search")

    df_filtered = df_all.copy()
    if f_priority != "Todas":
        df_filtered = df_filtered[df_filtered['priority'] == f_priority]
    if f_status != "Todos":
        df_filtered = df_filtered[df_filtered['status'] == f_status]
    if f_search:
        df_filtered = df_filtered[
            df_filtered['title'].str.contains(f_search, case=False, na=False)]

    n_main = len(df_filtered[df_filtered['parent_id'].isna()])
    st.markdown(f"**{n_main} atividade(s) principal(is)**")
    st.markdown("---")

    _render_activity_tree(df_filtered, df_all)


def _render_activity_tree(df_filtered: pd.DataFrame, df_all: pd.DataFrame):
    today     = date.today()
    main_acts = df_filtered[df_filtered['parent_id'].isna()]
    for _, act in main_acts.iterrows():
        _render_activity_row(act, today, depth=0)
        _render_children(df_all, int(act['id']), today, depth=1)


def _render_children(df: pd.DataFrame, parent_id: int,
                     today: date, depth: int, max_depth: int = 5):
    if depth > max_depth:
        return
    def _matches(val) -> bool:
        if val is None: return False
        try:
            if isinstance(val, float) and pd.isna(val): return False
            return int(val) == int(parent_id)
        except (ValueError, TypeError): return False
    children = df[df['parent_id'].apply(_matches)]
    for _, child in children.iterrows():
        _render_activity_row(child, today, depth=depth)
        _render_children(df, int(child['id']), today, depth + 1, max_depth)


def _render_activity_row(row, today: date, depth: int = 0):
    act_id     = int(row['id'])
    is_editing = _get_editing_id() == act_id
    if is_editing:
        _render_edit_form(row, depth=depth)
    else:
        _render_view_row(row, today, depth)


def _render_view_row(row, today: date, depth: int = 0):
    from utils.helpers import priority_emoji, status_icon, fmt_date
    act_id = int(row['id'])
    is_sub = depth > 0

    end_d = row.get('end_date')
    if end_d and not isinstance(end_d, date):
        try:    end_d = pd.to_datetime(end_d).date()
        except: end_d = None

    icon    = status_icon(row.get('status', ''), end_d)
    p_emoji = priority_emoji(row.get('priority', ''))
    desc    = str(row.get('description') or '').strip()
    desc_html = (
        f'<div style="font-size:12px;color:#94A3B8;margin-top:3px;'
        f'padding-left:6px;border-left:2px solid #334155">{desc}</div>'
        if desc else ''
    )

    if is_sub:
        indent_w = min(depth * 0.6, 1.8)
        info_w   = max(5.0 - indent_w, 2.5)
        all_cols = st.columns([indent_w, info_w, 2, 2, 1, 1])
        with all_cols[0]:
            st.markdown(
                f'<div style="border-left:3px solid #3B82F6;height:54px;'
                f'margin-left:{(depth-1)*8}px;margin-top:4px"></div>',
                unsafe_allow_html=True,
            )
        col_info, col_status, col_dates, col_edit, col_del = (
            all_cols[1], all_cols[2], all_cols[3], all_cols[4], all_cols[5])
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
        if new_status != cur_status:
            upsert_activity(dict(
                id=act_id, title=row['title'], status=new_status,
                priority=row.get('priority'), start_date=row.get('start_date'),
                end_date=row.get('end_date'), parent_id=row.get('parent_id'),
                description=str(row.get('description') or '').strip() or None,
            ))
            st.toast(f"Status → {new_status}", icon="✅")
            _reload()

    with col_dates:
        overdue = end_d and end_d < today and row.get('status') != 'Concluído'
        color   = "#EF4444" if overdue else "#94A3B8"
        st.markdown(f"""
        <div style="font-size:12px;color:{color};padding:8px 0">
            📅 {fmt_date(row.get('start_date'))} → {fmt_date(end_d)}
        </div>
        """, unsafe_allow_html=True)

    with col_edit:
        if st.button("✏️", key=f"edit_act_{act_id}", help="Editar"):
            _set_editing_id(act_id)
            st.rerun()

    with col_del:
        if st.button("🗑️", key=f"del_act_{act_id}", help="Excluir"):
            delete_activity(act_id)
            st.toast("🗑️ Excluída.", icon="🗑️")
            _reload()


def _render_edit_form(row, depth: int = 0):
    from utils.helpers import fmt_date
    act_id = int(row['id'])
    k      = f"edt_{act_id}"

    cur_title  = str(row.get('title', ''))
    cur_desc   = str(row.get('description') or '')
    cur_start  = row.get('start_date')
    cur_end    = row.get('end_date')
    cur_prior  = row.get('priority', PRIORITIES[2])
    cur_status = row.get('status', STATUS_LIST[0])

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
        <span style="color:#60A5FA;font-weight:600">✏️ Editando: {cur_title}</span>
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
    if cs.button("💾 Salvar", key=f"{k}_save", type="primary", use_container_width=True):
        if new_title.strip():
            upsert_activity(dict(
                id=act_id, title=new_title.strip(),
                description=new_desc.strip() or None,
                start_date=new_start, end_date=new_end,
                priority=new_prior, status=new_status,
                parent_id=row.get('parent_id'),
            ))
            _set_editing_id(None)
            st.toast("✅ Atualizada!", icon="✅")
            _reload()
        else:
            st.error("Título obrigatório.")

    if cc.button("❌ Cancelar", key=f"{k}_cancel", use_container_width=True):
        _set_editing_id(None)
        st.rerun()

    st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# ABA 3 — PLANO DE AÇÃO (5W2H)
# ══════════════════════════════════════════════════════════════════════════════

def _tab_plano_acao():
    st.markdown("### 🗂️ Plano de Ação — 5W2H")

    df_acts = get_activities()
    act_options = {"— Nenhuma —": None}
    if not df_acts.empty:
        act_options.update({r['title']: r['id'] for _, r in df_acts.iterrows()})

    with st.expander("➕ Nova Ação 5W2H", expanded=False,
                     key=f"exp_5w2h_{st.session_state.get('_5w_key',0)}"):
        if '_5w_key' not in st.session_state: st.session_state['_5w_key'] = 0
        wk = st.session_state['_5w_key']
        with st.form(f"form_5w2h_{wk}", clear_on_submit=True):
            act_sel = st.selectbox("Vincular a Atividade", list(act_options.keys()))
            act_id  = act_options.get(act_sel)
            c1, c2  = st.columns(2)
            what        = c1.text_area("O quê? (What)*",  height=80)
            why         = c2.text_area("Por quê? (Why)",  height=80)
            who         = c1.text_input("Quem? (Who)")
            when_date   = c2.date_input("Quando? (When)")
            where_place = c1.text_input("Onde? (Where)")
            how         = c2.text_area("Como? (How)", height=80)
            how_much    = st.number_input("Quanto custa? (R$)", min_value=0.0, step=0.01)
            status_5w   = st.selectbox("Status",
                              ["Pendente","Em andamento","Concluído","Cancelado"])
            if st.form_submit_button("💾 Salvar", use_container_width=True):
                if what:
                    upsert_action_plan(dict(
                        activity_id=act_id, what=what, why=why, who=who,
                        when_date=when_date, where_place=where_place,
                        how=how, how_much=how_much, status=status_5w,
                    ))
                    st.toast("✅ Ação salva!", icon="✅")
                    st.session_state['_5w_key'] += 1
                    _reload()
                else:
                    st.error("'O quê?' é obrigatório.")

    df_plans = get_action_plans()
    if df_plans.empty:
        st.info("Nenhum plano de ação cadastrado.")
        return

    st.markdown(f"**{len(df_plans)} ação(ões)**")

    cols_edit = ['id','activity_title','what','who','when_date','status','how_much']
    existing  = [c for c in cols_edit if c in df_plans.columns]
    df_show   = df_plans[existing].copy()
    df_show.insert(0, 'Excluir', False)
    if 'when_date' in df_show.columns:
        df_show['when_date'] = pd.to_datetime(
            df_show['when_date'], errors='coerce').dt.strftime('%d/%m/%Y')
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
            "Custo (R$)": st.column_config.NumberColumn("Custo (R$)",
                              format="R$ %.2f", disabled=True),
        },
    )

    to_delete = edited[edited['Excluir'] == True]['id'].tolist()
    c_del, c_save = st.columns(2)

    if c_del.button(f"🗑️ Excluir ({len(to_delete)})",
                    disabled=(len(to_delete) == 0), use_container_width=True):
        for rid in to_delete:
            delete_action_plan(int(rid))
        st.toast(f"🗑️ {len(to_delete)} excluída(s).", icon="🗑️")
        _reload()

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
        _reload()


# ══════════════════════════════════════════════════════════════════════════════
# ABA CALENDÁRIO
# ══════════════════════════════════════════════════════════════════════════════

EVENT_TYPES = {
    "Trabalho":       "#3B82F6",
    "Reunião":        "#8B5CF6",
    "Pessoal":        "#10B981",
    "Saúde":          "#EF4444",
    "Estudo":         "#F59E0B",
    "Visita Técnica": "#06B6D4",
    "Outro":          "#64748B",
    "Tarefa":         "#475569",
}

WEEK_PT   = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
MONTH_PT  = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
             "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]

HOUR_START = 6
HOUR_END   = 22
HOUR_PX    = 48   # pixels per hour in weekly view


def _tab_calendario():
    # ── State ────────────────────────────────────────────────────────────────
    if '_cal_view'     not in st.session_state: st.session_state['_cal_view']     = 'weekly'
    if '_cal_ref'      not in st.session_state: st.session_state['_cal_ref']      = date.today()
    if '_cal_new_date' not in st.session_state: st.session_state['_cal_new_date'] = date.today()
    if '_cal_edit_id'  not in st.session_state: st.session_state['_cal_edit_id']  = None

    view = st.session_state['_cal_view']
    ref  = st.session_state['_cal_ref']

    # ── Barra de navegação ────────────────────────────────────────────────────
    nav1, nav2, nav3, nav4, nav5 = st.columns([1, 1, 4, 1, 1])

    if nav1.button("◀", key="cal_prev", use_container_width=True):
        delta = timedelta(days=7) if view == 'weekly' else relativedelta(months=1)
        st.session_state['_cal_ref'] = ref - delta
        st.rerun()

    if nav5.button("▶", key="cal_next", use_container_width=True):
        delta = timedelta(days=7) if view == 'weekly' else relativedelta(months=1)
        st.session_state['_cal_ref'] = ref + delta
        st.rerun()

    # Label central
    if view == 'weekly':
        ws = ref - timedelta(days=ref.weekday())
        we = ws + timedelta(days=6)
        label = f"{ws.strftime('%d/%m')} — {we.strftime('%d/%m/%Y')}"
    else:
        label = f"{MONTH_PT[ref.month-1]} {ref.year}"

    nav3.markdown(
        f"<div style='text-align:center;font-size:16px;font-weight:600;"
        f"padding:6px;color:#F1F5F9'>{label}</div>",
        unsafe_allow_html=True,
    )

    # Toggle view
    vt1, vt2, vt3 = st.columns([2, 2, 6])
    if vt1.button("📆 Semanal", key="cal_wk_btn", use_container_width=True,
                  type="primary" if view == 'weekly' else "secondary"):
        st.session_state['_cal_view'] = 'weekly'
        st.rerun()
    if vt2.button("📅 Mensal", key="cal_mo_btn", use_container_width=True,
                  type="primary" if view == 'monthly' else "secondary"):
        st.session_state['_cal_view'] = 'monthly'
        st.rerun()
    if vt3.button("Hoje", key="cal_today_btn"):
        st.session_state['_cal_ref'] = date.today()
        st.rerun()

    st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)

    # ── Renderiza view ────────────────────────────────────────────────────────
    if view == 'weekly':
        _render_weekly(ref)
    else:
        _render_monthly(ref)

    st.markdown("---")
    _form_event()


# ─── VISUALIZAÇÃO SEMANAL ──────────────────────────────────────────────────────

def _render_weekly(ref: date):
    week_start = ref - timedelta(days=ref.weekday())
    week_dates = [week_start + timedelta(days=i) for i in range(7)]
    today = date.today()

    # Busca eventos da semana
    df_ev = get_calendar_events(week_dates[0], week_dates[6])
    events_by_day: dict = {d: [] for d in week_dates}
    if not df_ev.empty:
        for _, ev in df_ev.iterrows():
            ev_date = ev.get('start_date')
            if hasattr(ev_date, 'date'): ev_date = ev_date.date()
            if ev_date in events_by_day:
                events_by_day[ev_date].append(ev)

    total_height = (HOUR_END - HOUR_START) * HOUR_PX

    # ── Build HTML ────────────────────────────────────────────────────────────
    # Header
    header_days = ''
    for i, d in enumerate(week_dates):
        is_today = (d == today)
        day_color = "#60A5FA" if is_today else "#94A3B8"
        num_bg    = "#3B82F6" if is_today else "transparent"
        num_color = "#FFFFFF" if is_today else "#F1F5F9"
        header_days += (
            f'<div style="flex:1;text-align:center;padding:6px 2px;'
            f'border-left:1px solid #1E293B;">'
            f'<div style="font-size:11px;color:{day_color};text-transform:uppercase">{WEEK_PT[i]}</div>'
            f'<div style="display:inline-block;width:28px;height:28px;line-height:28px;'
            f'border-radius:50%;background:{num_bg};color:{num_color};'
            f'font-size:16px;font-weight:600;margin-top:2px">{d.day}</div>'
            f'</div>'
        )

    # Hour labels
    hour_labels = ''
    for h in range(HOUR_START, HOUR_END):
        top = (h - HOUR_START) * HOUR_PX
        hour_labels += (
            f'<div style="position:absolute;top:{top}px;left:0;right:0;'
            f'font-size:10px;color:#475569;padding:2px 4px;line-height:1">'
            f'{h:02d}:00</div>'
        )

    # Day columns with events
    day_cols_html = ''
    for d in week_dates:
        # Hour lines
        lines = ''
        for h in range(HOUR_END - HOUR_START):
            top = h * HOUR_PX
            lines += f'<div style="position:absolute;top:{top}px;left:0;right:0;height:1px;background:#1E293B;"></div>'

        # Half-hour lines (lighter)
        for h in range(HOUR_END - HOUR_START):
            top = h * HOUR_PX + HOUR_PX // 2
            lines += f'<div style="position:absolute;top:{top}px;left:0;right:0;height:1px;background:#0F172A;"></div>'

        # Current time indicator
        if d == today:
            now = datetime.now()
            mins_from_start = (now.hour - HOUR_START) * 60 + now.minute
            if 0 <= mins_from_start <= (HOUR_END - HOUR_START) * 60:
                top_now = mins_from_start / 60 * HOUR_PX
                lines += (
                    f'<div style="position:absolute;top:{top_now:.0f}px;left:0;right:0;'
                    f'height:2px;background:#EF4444;z-index:10;">'
                    f'<div style="position:absolute;left:-4px;top:-4px;width:8px;height:8px;'
                    f'border-radius:50%;background:#EF4444;"></div></div>'
                )

        # Events
        evs_html = ''
        for ev in events_by_day.get(d, []):
            st_obj = ev.get('start_time')
            et_obj = ev.get('end_time')
            color  = ev.get('event_color') or '#3B82F6'

            if st_obj is None: continue
            if hasattr(st_obj, 'hour'):
                sh, sm = st_obj.hour, st_obj.minute
            else:
                try: sh, sm = int(str(st_obj)[:2]), int(str(st_obj)[3:5])
                except: continue

            top_ev = max(0, (sh * 60 + sm - HOUR_START * 60) / 60 * HOUR_PX)

            if et_obj and hasattr(et_obj, 'hour'):
                eh, em = et_obj.hour, et_obj.minute
                dur_mins = (eh * 60 + em) - (sh * 60 + sm)
            elif et_obj:
                try:
                    eh, em = int(str(et_obj)[:2]), int(str(et_obj)[3:5])
                    dur_mins = (eh * 60 + em) - (sh * 60 + sm)
                except: dur_mins = 60
            else:
                dur_mins = 60

            dur_mins = max(30, dur_mins)
            height_ev = dur_mins / 60 * HOUR_PX

            status = str(ev.get('status', ''))
            opacity = '0.5' if status == 'Concluído' else '1'
            text_deco = 'line-through' if status == 'Concluído' else 'none'
            title_short = str(ev.get('title', ''))[:20]
            time_str = f"{sh:02d}:{sm:02d}"

            evs_html += (
                f'<div title="{ev.get("title","")}" style="position:absolute;top:{top_ev:.0f}px;'
                f'height:{height_ev:.0f}px;left:2px;right:2px;background:{color};'
                f'border-radius:4px;padding:2px 4px;overflow:hidden;cursor:pointer;'
                f'opacity:{opacity};z-index:5;">'
                f'<div style="font-size:10px;font-weight:600;color:#fff;'
                f'text-decoration:{text_deco};line-height:1.3">{title_short}</div>'
                f'<div style="font-size:9px;color:rgba(255,255,255,0.8)">{time_str}</div>'
                f'</div>'
            )

        day_cols_html += (
            f'<div style="flex:1;border-left:1px solid #1E293B;position:relative;height:{total_height}px;">'
            f'{lines}{evs_html}'
            f'</div>'
        )

    # Final HTML
    cal_html = f"""
<div style="font-family:Inter,sans-serif;background:#0F172A;border-radius:12px;
            border:1px solid #1E293B;overflow:hidden;">
  <div style="display:flex;border-bottom:1px solid #1E293B;background:#1E293B;">
    <div style="width:50px;flex-shrink:0;"></div>
    {header_days}
  </div>
  <div style="display:flex;overflow-y:auto;max-height:580px;">
    <div style="width:50px;flex-shrink:0;position:relative;height:{total_height}px;background:#0F172A;">
      {hour_labels}
    </div>
    {day_cols_html}
  </div>
</div>
"""
    import streamlit.components.v1 as stcomp
    stcomp.html(cal_html, height=640, scrolling=False)


# ─── VISUALIZAÇÃO MENSAL ───────────────────────────────────────────────────────

def _render_monthly(ref: date):
    today = date.today()
    month_start = ref.replace(day=1)
    month_end   = (month_start + relativedelta(months=1)) - timedelta(days=1)

    df_ev = get_calendar_events(month_start, month_end)
    events_by_day: dict = {}
    if not df_ev.empty:
        for _, ev in df_ev.iterrows():
            ev_date = ev.get('start_date')
            if hasattr(ev_date, 'date'): ev_date = ev_date.date()
            events_by_day.setdefault(ev_date, []).append(ev)

    # Header dias da semana
    header = st.columns(7)
    for i, d in enumerate(WEEK_PT):
        color = "#EF4444" if d == "Dom" else "#94A3B8"
        header[i].markdown(
            f"<div style='text-align:center;font-size:12px;font-weight:600;"
            f"color:{color};padding:4px 0'>{d}</div>",
            unsafe_allow_html=True,
        )

    # Dias do mês
    first_wd = month_start.weekday()
    days_in  = month_end.day
    all_days = [None] * first_wd + [
        month_start + timedelta(days=i) for i in range(days_in)
    ]
    weeks = [all_days[i:i+7] for i in range(0, len(all_days), 7)]
    if len(weeks[-1]) < 7:
        weeks[-1] += [None] * (7 - len(weeks[-1]))

    for week in weeks:
        cols = st.columns(7)
        for i, day in enumerate(week):
            with cols[i]:
                if day is None:
                    st.markdown("<div style='height:80px'></div>", unsafe_allow_html=True)
                    continue

                is_today  = (day == today)
                is_sunday = (i == 6)
                evs       = events_by_day.get(day, [])

                num_bg    = "#3B82F6" if is_today else "transparent"
                num_color = "#FFFFFF" if is_today else ("#EF4444" if is_sunday else "#F1F5F9")

                # Eventos pills
                ev_pills = ""
                for ev in evs[:3]:
                    c = ev.get('event_color') or '#3B82F6'
                    t = str(ev.get('title',''))[:10]
                    s = str(ev.get('status',''))
                    op = '0.5' if s == 'Concluído' else '1'
                    ev_pills += (
                        f'<div style="background:{c};color:#fff;font-size:9px;'
                        f'border-radius:3px;padding:1px 4px;margin-top:2px;'
                        f'overflow:hidden;white-space:nowrap;opacity:{op}">{t}</div>'
                    )
                if len(evs) > 3:
                    ev_pills += f'<div style="font-size:9px;color:#64748B;margin-top:2px">+{len(evs)-3} mais</div>'

                st.markdown(
                    f'<div style="border:1px solid #1E293B;border-radius:6px;'
                    f'padding:4px;min-height:78px;background:#0F172A;cursor:pointer">'
                    f'<div style="display:inline-block;width:22px;height:22px;line-height:22px;'
                    f'border-radius:50%;background:{num_bg};color:{num_color};'
                    f'font-size:12px;font-weight:600;text-align:center">{day.day}</div>'
                    f'{ev_pills}</div>',
                    unsafe_allow_html=True,
                )

                # Botão para ir à semana deste dia
                if st.button("", key=f"mo_day_{day}", help=f"Ver semana de {day.strftime('%d/%m')}",
                             use_container_width=True):
                    st.session_state['_cal_ref']  = day
                    st.session_state['_cal_view'] = 'weekly'
                    st.session_state['_cal_new_date'] = day
                    st.rerun()

        st.markdown("<div style='margin-bottom:2px'></div>", unsafe_allow_html=True)


# ─── FORMULÁRIO DE EVENTO ──────────────────────────────────────────────────────

def _form_event():
    """Cria ou edita evento — sincronizado automaticamente com a tabela de atividades."""
    edit_id = st.session_state.get('_cal_edit_id')

    # Se editando, busca dados existentes
    existing = None
    if edit_id:
        df_all = get_activities()
        rows   = df_all[df_all['id'] == edit_id] if not df_all.empty else pd.DataFrame()
        existing = rows.iloc[0] if not rows.empty else None

    title_form = "✏️ Editar Evento" if existing is not None else "➕ Novo Evento"
    with st.expander(title_form, expanded=(existing is not None),
                     key=f"exp_ev_{st.session_state.get('_ev_key',0)}"):

        if '_ev_key' not in st.session_state: st.session_state['_ev_key'] = 0
        ek = st.session_state['_ev_key']

        def _v(field, default):
            return existing.get(field, default) if existing is not None else default

        c1, c2 = st.columns(2)
        ev_title = c1.text_input("Título*", value=str(_v('title','')), key=f"ev_tit_{ek}")
        ev_type  = c2.selectbox("Tipo", list(EVENT_TYPES.keys()),
                                 index=list(EVENT_TYPES.keys()).index(str(_v('event_type','Tarefa')))
                                 if _v('event_type','Tarefa') in EVENT_TYPES else 0,
                                 key=f"ev_tp_{ek}")
        ev_color = EVENT_TYPES[ev_type]

        d1, d2 = st.columns(2)

        # Parse existing date
        def _parse_date(v):
            if v is None or (isinstance(v, float) and pd.isna(v)): return date.today()
            if hasattr(v, 'date'): return v.date()
            if isinstance(v, date): return v
            try: return pd.to_datetime(v).date()
            except: return date.today()

        ev_date  = d1.date_input("Data do evento*",
                                  value=_parse_date(_v('start_date', st.session_state.get('_cal_new_date', date.today()))),
                                  key=f"ev_dt_{ek}")

        # Parse existing time
        def _parse_time(v):
            if v is None or (isinstance(v, float) and pd.isna(v)): return None
            if hasattr(v, 'hour'): return v
            try:
                parts = str(v).split(':')
                return dtime(int(parts[0]), int(parts[1]))
            except: return None

        t1, t2 = st.columns(2)
        ev_start = t1.time_input("Início*", value=_parse_time(_v('start_time', dtime(8,0))) or dtime(8,0), key=f"ev_st_{ek}")
        ev_end   = t2.time_input("Fim",     value=_parse_time(_v('end_time',   dtime(9,0))) or dtime(9,0), key=f"ev_et_{ek}")

        ev_desc = st.text_area("Descrição", value=str(_v('description','') or ''),
                                height=60, key=f"ev_ds_{ek}")

        p1, p2 = st.columns(2)
        ev_priority = p1.selectbox("Prioridade", PRIORITIES,
                                    index=PRIORITIES.index(str(_v('priority','Importante não Urgente')))
                                    if _v('priority','Importante não Urgente') in PRIORITIES else 2,
                                    key=f"ev_pr_{ek}")
        ev_status   = p2.selectbox("Status", STATUS_LIST,
                                    index=STATUS_LIST.index(str(_v('status','Não iniciado')))
                                    if _v('status','Não iniciado') in STATUS_LIST else 0,
                                    key=f"ev_ss_{ek}")

        # Preview da cor
        st.markdown(
            f'<div style="background:{ev_color};border-radius:6px;padding:6px 12px;'
            f'display:inline-block;color:#fff;font-size:12px;margin-top:4px">'
            f'● {ev_type}</div>',
            unsafe_allow_html=True,
        )

        btn_lbl = "💾 Salvar evento" if existing is None else "💾 Atualizar evento"
        col_s, col_c = st.columns([2, 1]) if existing is not None else (st.columns([1, 0])[0], None)

        if (col_s if existing is None else col_s).button(
            btn_lbl, key=f"ev_btn_{ek}", type="primary", use_container_width=True
        ):
            if ev_title.strip():
                data = dict(
                    title       = ev_title.strip(),
                    description = ev_desc.strip() or None,
                    start_date  = ev_date,
                    end_date    = ev_date,
                    priority    = ev_priority,
                    status      = ev_status,
                    event_type  = ev_type,
                    event_color = ev_color,
                    start_time  = ev_start,
                    end_time    = ev_end,
                )
                if existing is not None:
                    data['id'] = int(existing['id'])
                    data['parent_id'] = existing.get('parent_id')

                upsert_activity(data)
                st.toast(f"✅ Evento '{ev_title}' {'atualizado' if existing else 'criado'}!", icon="📅")
                st.session_state['_ev_key'] += 1
                st.session_state['_cal_edit_id'] = None
                st.session_state['_cal_new_date'] = ev_date
                _reload()
            else:
                st.error("Título é obrigatório.")

        if existing is not None and col_c:
            if col_c.button("❌ Cancelar edição", key=f"ev_cancel_{ek}", use_container_width=True):
                st.session_state['_cal_edit_id'] = None
                st.rerun()

            st.markdown("---")
            if st.button(f"🗑️ Excluir este evento e atividade", key=f"ev_del_{ek}",
                          use_container_width=True):
                delete_activity(int(existing['id']))
                st.session_state['_cal_edit_id'] = None
                st.toast("🗑️ Evento excluído.", icon="🗑️")
                _reload()
