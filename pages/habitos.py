"""
pages/habitos.py
Página Hábitos — Ciclos de 90 dias com check diário, calendário e estatísticas

Abas:
  ✅ Check do Dia   — marcar hábitos de hoje com um clique
  📊 Visão Geral   — progresso de todos os hábitos ativos
  📅 Calendário    — grade 90 dias de um hábito específico
  ⚙️ Gerenciar     — CRUD hábitos + iniciar/encerrar ciclos
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from database.queries_habitos import (
    get_habits, upsert_habit, delete_habit,
    get_cycles, get_active_cycle, start_cycle, finish_cycle,
    get_checks, toggle_check, mark_check, get_today_habits,
    calculate_stats, _is_scheduled,
)
from components.styles import page_header

CATEGORIES = ["Saúde", "Exercício", "Alimentação", "Estudo",
              "Produtividade", "Finanças", "Mental", "Social", "Outro"]

WEEK_DAYS_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
WEEK_ABBR    = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

HABIT_COLORS = {
    "Azul":     "#3B82F6",
    "Verde":    "#10B981",
    "Roxo":     "#8B5CF6",
    "Laranja":  "#F59E0B",
    "Rosa":     "#EC4899",
    "Vermelho": "#EF4444",
    "Ciano":    "#06B6D4",
    "Amarelo":  "#EAB308",
}

HABIT_ICONS = ["🎯","💧","🏃","📚","🧘","🥗","😴","💪","✍️","🚭","💰","🌟","🎨","🎵","🤝"]


def _reload():
    st.cache_data.clear()
    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
def render():
    page_header("Hábitos", "Ciclos de 90 dias para transformação de hábitos", "🔄")

    tabs = st.tabs(["✅ Check do Dia", "📊 Visão Geral", "📅 Calendário", "⚙️ Gerenciar"])
    with tabs[0]: _tab_check_dia()
    with tabs[1]: _tab_visao_geral()
    with tabs[2]: _tab_calendario()
    with tabs[3]: _tab_gerenciar()


# ══════════════════════════════════════════════════════════════════════════════
# ABA 1 — CHECK DO DIA
# ══════════════════════════════════════════════════════════════════════════════

def _tab_check_dia():
    today = date.today()
    st.markdown(f"### ✅ Hábitos de hoje — {today.strftime('%d/%m/%Y (%A)').replace('Monday','Segunda').replace('Tuesday','Terça').replace('Wednesday','Quarta').replace('Thursday','Quinta').replace('Friday','Sexta').replace('Saturday','Sábado').replace('Sunday','Domingo')}")

    df = get_today_habits()
    if df.empty:
        st.info("Nenhum hábito com ciclo ativo. Crie hábitos na aba **⚙️ Gerenciar**.")
        return

    # Filtra hábitos programados para hoje
    today_habits = []
    for _, row in df.iterrows():
        if _is_scheduled(today, row.get('frequency_type','Diário'), row.get('frequency_days','')):
            today_habits.append(row)

    if not today_habits:
        st.info("Nenhum hábito programado para hoje.")
        return

    done_count  = sum(1 for r in today_habits if r.get('done_today'))
    total_count = len(today_habits)
    pct_today   = int(done_count / total_count * 100) if total_count > 0 else 0

    # Barra de progresso do dia
    st.markdown(f"""
    <div style="background:#1E293B;border-radius:12px;padding:16px 20px;margin-bottom:16px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <span style="color:#F1F5F9;font-weight:600">Progresso de hoje</span>
            <span style="color:#60A5FA;font-weight:700;font-size:20px">{done_count}/{total_count}</span>
        </div>
        <div style="background:#334155;border-radius:6px;height:10px">
            <div style="width:{pct_today}%;background:{'#10B981' if pct_today==100 else '#3B82F6'};
                        height:100%;border-radius:6px;transition:width 0.3s"></div>
        </div>
        <div style="color:#64748B;font-size:12px;margin-top:6px">
            {"🎉 Todos os hábitos concluídos hoje!" if pct_today==100 else f"{pct_today}% concluídos"}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Cards de hábitos
    for row in today_habits:
        cycle_id = int(row['cycle_id'])
        habit_id = int(row['habit_id'])
        done     = bool(row.get('done_today', False))
        color    = row.get('color', '#3B82F6')
        icon     = row.get('icon', '🎯')

        # Busca streak rápido
        df_checks = get_checks(cycle_id)
        habit_data = {'frequency_type': row.get('frequency_type','Diário'),
                      'frequency_days': row.get('frequency_days','')}
        cycle_data = {'start_date': row['start_date'], 'end_date': row['end_date']}
        stats = calculate_stats(cycle_data, df_checks, habit_data)
        streak = stats['current_streak']

        # Card
        bg    = "#0F3D2E" if done else "#1E293B"
        border = color if done else "#334155"
        check_emoji = "✅" if done else "⬜"

        col_card, col_btn = st.columns([5, 1])
        with col_card:
            st.markdown(f"""
            <div style="background:{bg};border-radius:12px;padding:12px 16px;
                        border:1px solid {border};margin-bottom:6px">
                <div style="display:flex;align-items:center;gap:10px">
                    <span style="font-size:24px">{icon}</span>
                    <div style="flex:1">
                        <div style="color:#F1F5F9;font-weight:600">{row['name']}</div>
                        <div style="color:#64748B;font-size:12px">
                            {row.get('category','')}
                            {"  🔥 " + str(streak) + " dias seguidos" if streak > 1 else ""}
                        </div>
                    </div>
                    <span style="font-size:22px">{check_emoji}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        with col_btn:
            btn_label = "↩️" if done else "✔️"
            btn_help  = "Desmarcar" if done else "Marcar como feito"
            if st.button(btn_label, key=f"chk_{habit_id}_{today}",
                         help=btn_help, use_container_width=True):
                toggle_check(cycle_id, today)
                _reload()

    if done_count == total_count and total_count > 0:
        st.balloons()


# ══════════════════════════════════════════════════════════════════════════════
# ABA 2 — VISÃO GERAL
# ══════════════════════════════════════════════════════════════════════════════

def _tab_visao_geral():
    st.markdown("### 📊 Progresso dos Hábitos")
    df_habits = get_habits()
    if df_habits.empty:
        st.info("Nenhum hábito cadastrado. Crie em **⚙️ Gerenciar**.")
        return

    for _, habit in df_habits.iterrows():
        habit_id = int(habit['id'])
        cycle    = get_active_cycle(habit_id)
        if not cycle:
            continue

        cycle_id  = int(cycle['id'])
        df_checks = get_checks(cycle_id)
        stats     = calculate_stats(cycle, df_checks, dict(habit))
        color     = habit.get('color', '#3B82F6')
        icon      = habit.get('icon', '🎯')

        start = cycle['start_date']
        end   = cycle['end_date']
        if hasattr(start, 'date'): start = start.date()
        if hasattr(end, 'date'):   end   = end.date()

        with st.expander(
            f"{icon} **{habit['name']}** — {stats['pct_done']}% ✅  "
            f"| 🔥 {stats['current_streak']} dias | {stats['days_remaining']} restantes",
            expanded=False,
        ):
            # ── KPIs ──────────────────────────────────────────────────────
            k1, k2, k3, k4, k5 = st.columns(5)
            _stat_card(k1, "✅ Realizados",    f"{stats['done']}",             f"de {stats['total_programmed']} dias",  color)
            _stat_card(k2, "❌ Não realizados", f"{stats['total_programmed'] - stats['done']}", "dias perdidos", "#EF4444")
            _stat_card(k3, "📈 % Realizado",   f"{stats['pct_done']}%",        "",              "#10B981" if stats['pct_done'] >= 80 else "#F59E0B")
            _stat_card(k4, "🔥 Streak atual",  f"{stats['current_streak']}",   "dias seguidos", "#F59E0B")
            _stat_card(k5, "🏆 Melhor streak", f"{stats['best_streak']}",      "dias",          "#8B5CF6")

            # ── Barra de progresso 90 dias ─────────────────────────────────
            st.markdown(f"""
            <div style="margin:12px 0 4px 0;color:#94A3B8;font-size:12px">
                Progresso do ciclo: {stats['days_elapsed']} / 90 dias
                ({start.strftime('%d/%m/%Y')} → {end.strftime('%d/%m/%Y')})
            </div>
            <div style="background:#334155;border-radius:6px;height:8px;margin-bottom:12px">
                <div style="width:{stats['progress_pct']}%;background:{color};
                            height:100%;border-radius:6px"></div>
            </div>
            """, unsafe_allow_html=True)

            # ── Gráfico de rosca ──────────────────────────────────────────
            c_donut, c_bar = st.columns([1, 2])
            with c_donut:
                done_v   = stats['done']
                missed_v = max(0, stats['total_programmed'] - stats['done'])
                future_v = max(0, stats['days_remaining'])
                fig = go.Figure(go.Pie(
                    labels=["Realizado", "Não realizado", "Restante"],
                    values=[done_v, missed_v, future_v],
                    marker_colors=[color, "#EF4444", "#334155"],
                    hole=0.6,
                    textinfo='percent',
                    hoverinfo='label+value',
                ))
                fig.update_layout(
                    height=200, margin=dict(l=0,r=0,t=0,b=0),
                    paper_bgcolor='rgba(0,0,0,0)', font_color='#94A3B8',
                    showlegend=False,
                    annotations=[dict(text=f"{stats['pct_done']}%",
                                      x=0.5, y=0.5, font_size=18,
                                      font_color='#F1F5F9', showarrow=False)],
                )
                st.plotly_chart(fig, use_container_width=True)

            with c_bar:
                # Mini heatmap dos últimos 30 dias
                _render_mini_heatmap(df_checks, cycle, dict(habit), color)


def _stat_card(col, title, value, sub, color):
    col.markdown(f"""
    <div style="background:#1E293B;border-radius:10px;padding:12px;
                border-top:3px solid {color};text-align:center">
        <div style="color:#64748B;font-size:11px">{title}</div>
        <div style="color:#F1F5F9;font-size:22px;font-weight:700">{value}</div>
        <div style="color:#64748B;font-size:11px">{sub}</div>
    </div>
    """, unsafe_allow_html=True)


def _render_mini_heatmap(df_checks: pd.DataFrame, cycle: dict, habit: dict, color: str):
    """Mini grade dos últimos 30 dias."""
    today = date.today()
    start = cycle['start_date']
    if hasattr(start, 'date'): start = start.date()

    checks_by_date = {}
    if not df_checks.empty:
        for _, row in df_checks.iterrows():
            d = row['check_date']
            if hasattr(d, 'date'): d = d.date()
            checks_by_date[d] = bool(row.get('done', False))

    # Últimos 35 dias dentro do ciclo
    range_start = max(start, today - timedelta(days=34))
    days = [(range_start + timedelta(days=i))
            for i in range((today - range_start).days + 1)]

    # Header dias da semana
    st.markdown("<small style='color:#64748B'>Últimos 35 dias:</small>", unsafe_allow_html=True)
    cols = st.columns(7)
    for i, abbr in enumerate(WEEK_ABBR):
        cols[i].markdown(f"<div style='text-align:center;font-size:10px;color:#64748B'>{abbr}</div>",
                         unsafe_allow_html=True)

    # Preenche semanas
    week_start_wd = range_start.weekday()
    padded = [None] * week_start_wd + days
    weeks  = [padded[i:i+7] for i in range(0, len(padded), 7)]

    for week in weeks:
        cols = st.columns(7)
        for i, day in enumerate(week):
            with cols[i]:
                if day is None:
                    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
                    continue
                scheduled = _is_scheduled(day, habit.get('frequency_type','Diário'),
                                          habit.get('frequency_days',''))
                done = checks_by_date.get(day, False)
                is_today = day == today
                is_past  = day < today

                if not scheduled:
                    bg = "#0F172A"
                elif done:
                    bg = color
                elif is_past:
                    bg = "#7F1D1D"
                else:
                    bg = "#1E293B"

                border = "2px solid #F1F5F9" if is_today else "1px solid #334155"
                st.markdown(f"""
                <div style="background:{bg};border:{border};border-radius:4px;
                            height:22px;width:100%;margin:1px 0;
                            display:flex;align-items:center;justify-content:center;
                            font-size:9px;color:#94A3B8">{day.day}</div>
                """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# ABA 3 — CALENDÁRIO 90 DIAS
# ══════════════════════════════════════════════════════════════════════════════

def _tab_calendario():
    st.markdown("### 📅 Calendário — 90 dias")
    df_habits = get_habits()
    if df_habits.empty:
        st.info("Nenhum hábito cadastrado.")
        return

    # Seleciona hábito
    habits_with_cycle = []
    for _, h in df_habits.iterrows():
        if get_active_cycle(int(h['id'])):
            habits_with_cycle.append(h)

    if not habits_with_cycle:
        st.info("Nenhum hábito com ciclo ativo. Inicie um ciclo em **⚙️ Gerenciar**.")
        return

    habit_map = {f"{h['icon']} {h['name']}": int(h['id']) for h in habits_with_cycle}
    sel = st.selectbox("Hábito", list(habit_map.keys()), key="cal_habit_sel")
    habit_id   = habit_map[sel]
    habit_row  = df_habits[df_habits['id'] == habit_id].iloc[0]
    cycle      = get_active_cycle(habit_id)
    cycle_id   = int(cycle['id'])
    df_checks  = get_checks(cycle_id)
    color      = habit_row.get('color', '#3B82F6')

    start = cycle['start_date']
    end   = cycle['end_date']
    if hasattr(start, 'date'): start = start.date()
    if hasattr(end,   'date'): end   = end.date()
    today = date.today()

    checks_by_date = {}
    if not df_checks.empty:
        for _, row in df_checks.iterrows():
            d = row['check_date']
            if hasattr(d, 'date'): d = d.date()
            checks_by_date[d] = bool(row.get('done', False))

    # Stats resumidas
    stats = calculate_stats(cycle, df_checks, dict(habit_row))
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("✅ Realizados",    f"{stats['done']} dias")
    s2.metric("📈 % Realizado",   f"{stats['pct_done']}%")
    s3.metric("🔥 Streak atual",  f"{stats['current_streak']} dias")
    s4.metric("⏳ Restam",        f"{stats['days_remaining']} dias")

    st.markdown("---")
    st.markdown(f"**Ciclo:** {start.strftime('%d/%m/%Y')} → {end.strftime('%d/%m/%Y')}  "
                f"| Clique num dia para marcar/desmarcar")

    # Legenda
    lc1, lc2, lc3, lc4 = st.columns(4)
    lc1.markdown(f"<span style='background:{color};padding:2px 10px;border-radius:4px;font-size:12px'>✅ Feito</span>", unsafe_allow_html=True)
    lc2.markdown("<span style='background:#7F1D1D;padding:2px 10px;border-radius:4px;font-size:12px'>❌ Não feito</span>", unsafe_allow_html=True)
    lc3.markdown("<span style='background:#1E293B;border:1px solid #3B82F6;padding:2px 10px;border-radius:4px;font-size:12px'>📍 Hoje</span>", unsafe_allow_html=True)
    lc4.markdown("<span style='background:#0F172A;padding:2px 10px;border-radius:4px;font-size:12px'>⬜ Futuro</span>", unsafe_allow_html=True)
    st.markdown("")

    # Renderiza 3 meses
    for month_offset in range(3):
        month_date  = start + relativedelta(months=month_offset)
        month_start = month_date.replace(day=1)
        next_month  = month_start + relativedelta(months=1)
        month_end   = next_month - timedelta(days=1)

        # Intersecta com ciclo
        render_start = max(start, month_start)
        render_end   = min(end,   month_end)
        if render_start > render_end:
            continue

        st.markdown(f"#### {month_start.strftime('%B %Y').capitalize()}")

        # Header dias da semana
        header_cols = st.columns(7)
        for i, abbr in enumerate(WEEK_ABBR):
            header_cols[i].markdown(
                f"<div style='text-align:center;font-weight:600;color:#94A3B8;font-size:13px'>{abbr}</div>",
                unsafe_allow_html=True)

        # Preenche semanas do mês
        days_in_month = [(render_start + timedelta(days=i))
                         for i in range((render_end - render_start).days + 1)]
        first_wd   = render_start.weekday()
        padded     = [None] * first_wd + days_in_month
        weeks      = [padded[i:i+7] for i in range(0, len(padded), 7)]

        for week in weeks:
            wc = st.columns(7)
            for i, day in enumerate(week):
                with wc[i]:
                    if day is None:
                        st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)
                        continue

                    scheduled = _is_scheduled(day, habit_row.get('frequency_type','Diário'),
                                              habit_row.get('frequency_days',''))
                    done      = checks_by_date.get(day, False)
                    is_today  = day == today
                    is_past   = day < today
                    is_future = day > today

                    if not scheduled:
                        # Dia não programado — mostra mas não clicável
                        st.markdown(f"""
                        <div style="background:#0F172A;border-radius:6px;height:40px;
                                    display:flex;align-items:center;justify-content:center;
                                    font-size:12px;color:#334155">{day.day}</div>
                        """, unsafe_allow_html=True)
                        continue

                    # Botão clicável
                    if done:
                        btn_style = f"background-color:{color};color:white;border:none"
                        label = f"✓ {day.day}"
                    elif is_today:
                        btn_style = "background-color:#1E3A5F;color:#60A5FA;border:2px solid #3B82F6"
                        label = f"📍{day.day}"
                    elif is_past:
                        btn_style = "background-color:#7F1D1D;color:#FCA5A5;border:none"
                        label = f"✗ {day.day}"
                    else:
                        btn_style = "background-color:#1E293B;color:#64748B;border:1px solid #334155"
                        label = str(day.day)

                    if st.button(label, key=f"cal_{cycle_id}_{day}",
                                 help=f"{'Desmarcar' if done else 'Marcar'} {day.strftime('%d/%m')}",
                                 use_container_width=True):
                        toggle_check(cycle_id, day)
                        _reload()

        st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# ABA 4 — GERENCIAR
# ══════════════════════════════════════════════════════════════════════════════

def _tab_gerenciar():
    st.markdown("### ⚙️ Gerenciar Hábitos")
    sub = st.radio("", ["➕ Criar Hábito", "🔄 Ciclos", "📋 Todos os Hábitos"],
                   horizontal=True, label_visibility="collapsed", key="ger_sub")

    if sub == "➕ Criar Hábito":   _form_new_habit()
    elif sub == "🔄 Ciclos":       _manage_cycles()
    else:                          _list_habits()


def _form_new_habit():
    st.markdown("#### Novo Hábito")
    if '_hab_key' not in st.session_state: st.session_state['_hab_key'] = 0
    k = st.session_state['_hab_key']

    c1, c2 = st.columns([3, 1])
    name = c1.text_input("Nome do hábito*", placeholder="Ex: Beber 2L de água", key=f"hn_{k}")
    icon = c2.selectbox("Ícone", HABIT_ICONS, key=f"hi_{k}")

    desc = st.text_area("Descrição / Objetivo", height=60, key=f"hd_{k}",
                         placeholder="Por que este hábito é importante para você?")

    cc1, cc2, cc3 = st.columns(3)
    category   = cc1.selectbox("Categoria", CATEGORIES, key=f"hcat_{k}")
    color_name = cc2.selectbox("Cor", list(HABIT_COLORS.keys()), key=f"hcol_{k}")
    color      = HABIT_COLORS[color_name]

    freq_type = cc3.selectbox("Frequência", ["Diário", "Dias da semana", "X vezes por semana"],
                               key=f"hft_{k}")
    freq_days = None
    if freq_type == "Dias da semana":
        sel_days = st.multiselect("Dias da semana", WEEK_DAYS_PT, default=WEEK_DAYS_PT[:5],
                                   key=f"hfd_{k}")
        # Converte para índices (0=Segunda)
        freq_days = ",".join(str(WEEK_DAYS_PT.index(d)) for d in sel_days) if sel_days else "0,1,2,3,4"
    elif freq_type == "X vezes por semana":
        x = st.slider("Quantas vezes por semana?", 1, 7, 3, key=f"hfx_{k}")
        freq_days = str(x)

    # Preview do hábito
    st.markdown(f"""
    <div style="background:#1E293B;border-radius:12px;padding:14px 18px;
                border-left:4px solid {color};margin:12px 0">
        <span style="font-size:24px">{icon}</span>
        <span style="color:#F1F5F9;font-weight:600;margin-left:10px">{name or 'Nome do hábito'}</span>
        <br>
        <span style="color:#64748B;font-size:12px">{category} · {freq_type}</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**Iniciar ciclo de 90 dias:**")
    start_d = st.date_input("Data de início", value=date.today(), key=f"hstart_{k}")
    end_d   = start_d + timedelta(days=89)
    st.caption(f"O ciclo vai de **{start_d.strftime('%d/%m/%Y')}** até **{end_d.strftime('%d/%m/%Y')}**")

    if st.button("🚀 Criar Hábito e Iniciar Ciclo", key=f"hbtn_{k}",
                 type="primary", use_container_width=True):
        if name.strip():
            habit_id = upsert_habit(dict(
                name=name.strip(), description=desc.strip() or None,
                category=category, frequency_type=freq_type,
                frequency_days=freq_days, color=color, icon=icon,
            ))
            if habit_id:
                start_cycle(int(habit_id), start_d)
                st.toast(f"✅ Hábito '{name}' criado com ciclo de 90 dias!", icon="🚀")
                st.session_state['_hab_key'] += 1
                _reload()
        else:
            st.error("Nome é obrigatório.")


def _manage_cycles():
    st.markdown("#### Ciclos de 90 dias")
    df_habits = get_habits()
    if df_habits.empty:
        st.info("Nenhum hábito criado.")
        return

    habit_map = dict(zip(df_habits['name'], df_habits['id']))
    sel = st.selectbox("Hábito", list(habit_map.keys()), key="cyc_sel")
    habit_id = int(habit_map[sel])
    habit_row = df_habits[df_habits['id'] == habit_id].iloc[0]

    # Ciclo ativo
    active_cycle = get_active_cycle(habit_id)
    if active_cycle:
        start = active_cycle['start_date']
        end   = active_cycle['end_date']
        if hasattr(start, 'date'): start = start.date()
        if hasattr(end,   'date'): end   = end.date()
        today = date.today()
        days_done = (today - start).days + 1
        days_left = max(0, (end - today).days)

        st.markdown(f"""
        <div style="background:#0F3D2E;border-radius:12px;padding:16px 20px;
                    border:1px solid #10B981;margin-bottom:16px">
            <div style="color:#6EE7B7;font-weight:600">🔄 Ciclo em andamento</div>
            <div style="color:#94A3B8;font-size:13px;margin-top:4px">
                {start.strftime('%d/%m/%Y')} → {end.strftime('%d/%m/%Y')}
                &nbsp;·&nbsp; Dia {min(days_done, 90)} de 90 &nbsp;·&nbsp; {days_left} dias restantes
            </div>
        </div>
        """, unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        if c1.button("✅ Concluir ciclo", use_container_width=True):
            finish_cycle(int(active_cycle['id']), 'Concluído')
            st.toast("🏆 Ciclo concluído! Parabéns!", icon="🏆")
            _reload()
        if c2.button("🚫 Abandonar ciclo", use_container_width=True):
            finish_cycle(int(active_cycle['id']), 'Abandonado')
            st.toast("Ciclo abandonado.", icon="🚫")
            _reload()
    else:
        st.warning("Nenhum ciclo ativo para este hábito.")
        new_start = st.date_input("Iniciar novo ciclo em:", value=date.today(), key="new_cycle_start")
        end_d = new_start + timedelta(days=89)
        st.caption(f"Duração: {new_start.strftime('%d/%m/%Y')} → {end_d.strftime('%d/%m/%Y')}")
        if st.button("🚀 Iniciar novo ciclo de 90 dias", type="primary", use_container_width=True):
            start_cycle(habit_id, new_start)
            st.toast("✅ Novo ciclo iniciado!", icon="🚀")
            _reload()

    # Histórico de ciclos
    df_cycles = get_cycles(habit_id)
    if not df_cycles.empty and len(df_cycles) > 1:
        with st.expander("📜 Histórico de ciclos", expanded=False):
            show = df_cycles[['start_date','end_date','status']].copy()
            show = show.rename(columns={'start_date':'Início','end_date':'Fim','status':'Status'})
            st.dataframe(show, hide_index=True, use_container_width=True)


def _list_habits():
    st.markdown("#### Todos os Hábitos")
    df_habits = get_habits()
    if df_habits.empty:
        st.info("Nenhum hábito cadastrado.")
        return

    for _, habit in df_habits.iterrows():
        habit_id = int(habit['id'])
        color    = habit.get('color', '#3B82F6')
        icon     = habit.get('icon', '🎯')
        cycle    = get_active_cycle(habit_id)
        status   = "🔄 Ativo" if cycle else "⏸️ Sem ciclo"

        col_info, col_del = st.columns([5, 1])
        with col_info:
            st.markdown(f"""
            <div style="background:#1E293B;border-radius:10px;padding:10px 14px;
                        border-left:4px solid {color};margin-bottom:6px">
                <b style="color:#F1F5F9">{icon} {habit['name']}</b>
                <span style="color:#64748B;font-size:12px;margin-left:10px">{status}</span>
                <br>
                <span style="color:#64748B;font-size:12px">
                    {habit.get('category','')} · {habit.get('frequency_type','Diário')}
                </span>
            </div>
            """, unsafe_allow_html=True)
        with col_del:
            if st.button("🗑️", key=f"del_hab_{habit_id}", help="Excluir hábito"):
                delete_habit(habit_id)
                st.toast("🗑️ Hábito excluído.", icon="🗑️")
                _reload()
