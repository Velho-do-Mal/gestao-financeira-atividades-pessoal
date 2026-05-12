"""
pages/atividades.py
Página Atividades — Gestão de Tarefas, Plano de Ação (5W2H) e Pomodoro
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import time

from database.queries import (
    get_activities, upsert_activity, delete_activity,
    get_action_plans, upsert_action_plan, delete_action_plan,
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

    tabs = st.tabs([
        "📋 Atividades",
        "🗂️ Plano de Ação (5W2H)",
        "🍅 Pomodoro",
    ])

    with tabs[0]:
        _tab_atividades()
    with tabs[1]:
        _tab_plano_acao()
    with tabs[2]:
        _tab_pomodoro()


# ══════════════════════════════════════════════════════════════════
# ABA 1 — ATIVIDADES
# ══════════════════════════════════════════════════════════════════
def _tab_atividades():
    st.markdown("### 📋 Gerenciamento de Atividades")

    # Formulário de nova atividade
    with st.expander("➕ Nova Atividade", expanded=False):
        df_acts = get_activities()
        parent_options = {"— Nenhuma (atividade principal) —": None}
        if not df_acts.empty:
            main_acts = df_acts[df_acts['parent_id'].isna()]
            parent_options.update({f"{r['title']}": r['id'] for _, r in main_acts.iterrows()})

        with st.form("form_activity", clear_on_submit=True):
            title = st.text_input("Título da Atividade*")
            description = st.text_area("Descrição", height=60)
            parent_sel = st.selectbox("Atividade Pai (subatividade?)", list(parent_options.keys()))
            parent_id = parent_options.get(parent_sel)

            c1, c2, c3, c4 = st.columns(4)
            start_date = c1.date_input("Início", value=date.today())
            end_date = c2.date_input("Conclusão", value=date.today() + timedelta(days=7))
            priority = c3.selectbox("Prioridade", PRIORITIES, index=2)
            status = c4.selectbox("Status", STATUS_LIST)

            if st.form_submit_button("💾 Salvar"):
                if title:
                    upsert_activity(dict(
                        title=title, description=description, parent_id=parent_id,
                        start_date=start_date, end_date=end_date,
                        priority=priority, status=status,
                    ))
                    st.success("Atividade salva!")
                    st.rerun()
                else:
                    st.error("Título é obrigatório.")

    # Exibição da lista de atividades
    df = get_activities()
    if df.empty:
        st.info("Nenhuma atividade cadastrada. Crie sua primeira atividade acima!")
        return

    # Filtros
    col_f1, col_f2, col_f3 = st.columns(3)
    f_priority = col_f1.selectbox("Filtrar Prioridade", ["Todas"] + PRIORITIES, key="f_prior")
    f_status = col_f2.selectbox("Filtrar Status", ["Todos"] + STATUS_LIST, key="f_stat")
    f_search = col_f3.text_input("Buscar", placeholder="Título...", key="f_search")

    df_filtered = df.copy()
    if f_priority != "Todas":
        df_filtered = df_filtered[df_filtered['priority'] == f_priority]
    if f_status != "Todos":
        df_filtered = df_filtered[df_filtered['status'] == f_status]
    if f_search:
        df_filtered = df_filtered[df_filtered['title'].str.contains(f_search, case=False, na=False)]

    # Exibir em tabela com hierarquia
    _render_activity_table(df_filtered)


def _render_activity_table(df: pd.DataFrame):
    """Renderiza atividades em formato hierárquico com ações."""
    today = date.today()

    # Separa atividades principais e subatividades
    main_acts = df[df['parent_id'].isna()].copy()
    sub_acts = df[df['parent_id'].notna()].copy()

    for _, act in main_acts.iterrows():
        _render_activity_row(act, today, indent=False)
        # Subatividades desta atividade
        subs = sub_acts[sub_acts['parent_id'] == act['id']]
        for _, sub in subs.iterrows():
            _render_activity_row(sub, today, indent=True)


def _render_activity_row(row, today, indent: bool = False):
    end_d = row.get('end_date')
    if end_d and not isinstance(end_d, date):
        try:
            end_d = pd.to_datetime(end_d).date()
        except Exception:
            end_d = None

    icon = status_icon(row.get('status', ''), end_d)
    p_emoji = priority_emoji(row.get('priority', ''))
    indent_style = "margin-left:32px;border-left:3px solid #3B82F6;padding-left:12px;" if indent else ""

    col_info, col_status, col_dates, col_del = st.columns([5, 2, 2, 1])

    with col_info:
        st.markdown(f"""
        <div style="padding:8px;{indent_style}">
            <span style="font-weight:{'500' if indent else '700'};color:{'#CBD5E1' if indent else '#F1F5F9'}">
                {icon} {p_emoji} {'&nbsp;&nbsp;&nbsp;&nbsp;' if indent else ''}{row['title']}
            </span>
            <br>
            <span style="font-size:11px;color:#64748B">{row.get('priority','')}</span>
        </div>
        """, unsafe_allow_html=True)

    with col_status:
        new_status = st.selectbox(
            "", STATUS_LIST,
            index=STATUS_LIST.index(row.get('status', 'Não iniciado')),
            key=f"stat_{row['id']}",
            label_visibility="collapsed"
        )
        if new_status != row.get('status'):
            upsert_activity(dict(
                id=int(row['id']), title=row['title'], status=new_status,
                priority=row.get('priority'), start_date=row.get('start_date'),
                end_date=row.get('end_date'), parent_id=row.get('parent_id'),
                description=row.get('description'),
            ))
            st.rerun()

    with col_dates:
        start_str = fmt_date(row.get('start_date'))
        end_str = fmt_date(end_d)
        date_color = "#EF4444" if (end_d and end_d < today and row.get('status') != 'Concluído') else "#94A3B8"
        st.markdown(f"""
        <div style="font-size:12px;color:{date_color};padding:8px 0">
            📅 {start_str} → {end_str}
        </div>
        """, unsafe_allow_html=True)

    with col_del:
        if st.button("🗑️", key=f"del_act_{row['id']}", help="Excluir atividade"):
            delete_activity(int(row['id']))
            st.rerun()


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
            act_id = act_options.get(act_sel)

            c1, c2 = st.columns(2)
            what = c1.text_area("O quê? (What)*", height=80, help="O que será feito?")
            why = c2.text_area("Por quê? (Why)", height=80, help="Por que deve ser feito?")
            who = c1.text_input("Quem? (Who)", help="Quem é o responsável?")
            when_date = c2.date_input("Quando? (When)")
            where_place = c1.text_input("Onde? (Where)", help="Onde será executado?")
            how = c2.text_area("Como? (How)", height=80, help="Como será feito?")
            how_much = st.number_input("Quanto custa? (How Much R$)", min_value=0.0, step=0.01)
            status = st.selectbox("Status", ["Pendente", "Em andamento", "Concluído", "Cancelado"])

            if st.form_submit_button("💾 Salvar"):
                if what:
                    upsert_action_plan(dict(
                        activity_id=act_id, what=what, why=why, who=who,
                        when_date=when_date, where_place=where_place, how=how,
                        how_much=how_much, status=status,
                    ))
                    st.success("Ação salva!")
                    st.rerun()
                else:
                    st.error("'O quê?' é obrigatório.")

    df_plans = get_action_plans()
    if df_plans.empty:
        st.info("Nenhum plano de ação cadastrado.")
        return

    # Exibir tabela
    cols_show = ['id', 'activity_title', 'what', 'why', 'who', 'when_date',
                 'where_place', 'how', 'how_much', 'status']
    existing = [c for c in cols_show if c in df_plans.columns]
    rename_map = {
        'id': 'ID', 'activity_title': 'Atividade',
        'what': 'O quê?', 'why': 'Por quê?', 'who': 'Quem?',
        'when_date': 'Quando?', 'where_place': 'Onde?',
        'how': 'Como?', 'how_much': 'Quanto?', 'status': 'Status',
    }

    df_show = df_plans[existing].rename(columns=rename_map)
    if 'Quanto?' in df_show.columns:
        df_show['Quando?'] = pd.to_datetime(df_show['Quando?']).dt.strftime('%d/%m/%Y') if 'Quando?' in df_show.columns else ''

    st.dataframe(
        df_show.style.format({'Quanto?': 'R$ {:,.2f}'}, subset=['Quanto?'] if 'Quanto?' in df_show.columns else []),
        use_container_width=True, hide_index=True, height=400
    )

    del_id = st.number_input("ID para excluir", min_value=0, step=1, key="del_plan")
    if st.button("🗑️ Excluir Ação"):
        if del_id > 0:
            delete_action_plan(int(del_id))
            st.rerun()


# ══════════════════════════════════════════════════════════════════
# ABA 3 — POMODORO
# ══════════════════════════════════════════════════════════════════
def _tab_pomodoro():
    st.markdown("### 🍅 Timer Pomodoro")

    # Configurações
    col_c1, col_c2 = st.columns(2)
    work_minutes = col_c1.number_input("⏱️ Tempo de Trabalho (minutos)", min_value=1, max_value=120, value=25)
    break_minutes = col_c2.number_input("☕ Tempo de Pausa (minutos)", min_value=1, max_value=60, value=5)

    # Estado do timer
    if 'pom_running' not in st.session_state:
        st.session_state.pom_running = False
    if 'pom_phase' not in st.session_state:
        st.session_state.pom_phase = 'work'  # 'work' | 'break'
    if 'pom_end_time' not in st.session_state:
        st.session_state.pom_end_time = None
    if 'pom_cycles' not in st.session_state:
        st.session_state.pom_cycles = 0

    # Display
    timer_placeholder = st.empty()
    phase_placeholder = st.empty()
    cycle_placeholder = st.empty()

    col_b1, col_b2, col_b3 = st.columns(3)
    with col_b1:
        if st.button("▶️ Iniciar" if not st.session_state.pom_running else "⏸️ Pausar", use_container_width=True):
            if not st.session_state.pom_running:
                duration = work_minutes if st.session_state.pom_phase == 'work' else break_minutes
                st.session_state.pom_end_time = time.time() + duration * 60
                st.session_state.pom_running = True
            else:
                st.session_state.pom_running = False

    with col_b2:
        if st.button("🔄 Reiniciar", use_container_width=True):
            st.session_state.pom_running = False
            st.session_state.pom_phase = 'work'
            st.session_state.pom_end_time = None
            st.rerun()

    with col_b3:
        if st.button("⏭️ Próxima Fase", use_container_width=True):
            st.session_state.pom_phase = 'break' if st.session_state.pom_phase == 'work' else 'work'
            if st.session_state.pom_phase == 'work':
                st.session_state.pom_cycles += 1
            st.session_state.pom_running = False
            st.session_state.pom_end_time = None
            st.rerun()

    # Timer loop
    phase_label = "🧠 Foco — Trabalhando" if st.session_state.pom_phase == 'work' else "☕ Pausa — Descanse!"
    phase_color = "#3B82F6" if st.session_state.pom_phase == 'work' else "#10B981"

    if st.session_state.pom_running and st.session_state.pom_end_time:
        remaining = st.session_state.pom_end_time - time.time()
        if remaining <= 0:
            # Fase concluída
            st.session_state.pom_running = False
            if st.session_state.pom_phase == 'work':
                st.session_state.pom_cycles += 1
                st.session_state.pom_phase = 'break'
                st.balloons()
                st.success("🎉 Pomodoro concluído! Hora da pausa.")
            else:
                st.session_state.pom_phase = 'work'
                st.info("☕ Pausa concluída. Vamos trabalhar!")

            # Bip (via JavaScript)
            st.markdown("""
            <script>
                try {
                    var ctx = new (window.AudioContext || window.webkitAudioContext)();
                    var osc = ctx.createOscillator();
                    var gain = ctx.createGain();
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.frequency.value = 880;
                    osc.type = 'sine';
                    gain.gain.setValueAtTime(0.5, ctx.currentTime);
                    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.8);
                    osc.start(ctx.currentTime);
                    osc.stop(ctx.currentTime + 0.8);
                } catch(e) {}
            </script>
            """, unsafe_allow_html=True)

            st.rerun()
        else:
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            timer_display = f"{mins:02d}:{secs:02d}"

            timer_placeholder.markdown(f"""
            <div style="text-align:center;padding:30px">
                <div style="font-family:'Space Mono',monospace;font-size:72px;font-weight:700;
                           color:{phase_color};letter-spacing:4px;
                           text-shadow:0 0 30px {phase_color}88">
                    {timer_display}
                </div>
                <div style="color:{phase_color};font-size:20px;margin-top:8px">{phase_label}</div>
            </div>
            """, unsafe_allow_html=True)

            cycle_placeholder.markdown(f"""
            <div style="text-align:center;color:#64748B;font-size:14px">
                🍅 Ciclos completos: <b>{st.session_state.pom_cycles}</b>
            </div>
            """, unsafe_allow_html=True)

            time.sleep(1)
            st.rerun()
    else:
        # Estado parado
        duration = work_minutes if st.session_state.pom_phase == 'work' else break_minutes
        timer_placeholder.markdown(f"""
        <div style="text-align:center;padding:30px">
            <div style="font-family:'Space Mono',monospace;font-size:72px;font-weight:700;
                       color:{phase_color};letter-spacing:4px;opacity:0.6">
                {duration:02d}:00
            </div>
            <div style="color:{phase_color};font-size:20px;margin-top:8px">{phase_label}</div>
        </div>
        """, unsafe_allow_html=True)

        cycle_placeholder.markdown(f"""
        <div style="text-align:center;color:#64748B;font-size:14px">
            🍅 Ciclos completos: <b>{st.session_state.pom_cycles}</b>
        </div>
        """, unsafe_allow_html=True)

    # Dicas pomodoro
    st.markdown("---")
    st.markdown("""
    <div style="background:#1E293B;border-radius:10px;padding:16px;border:1px solid #334155">
        <h4 style="color:#93C5FD;margin:0 0 10px 0">💡 Técnica Pomodoro</h4>
        <ul style="color:#94A3B8;margin:0;padding-left:20px">
            <li>Trabalhe com foco total durante o período de trabalho</li>
            <li>Faça uma pausa curta ao final de cada ciclo</li>
            <li>A cada 4 ciclos, faça uma pausa maior (15-30 min)</li>
            <li>Elimine distrações durante os períodos de foco</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
