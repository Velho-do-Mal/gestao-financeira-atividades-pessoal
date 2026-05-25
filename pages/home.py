"""
pages/home.py
Página Home — Painel de Controle BK Finance

RESPONSIVIDADE v2:
  - KPIs: kpi_row() → 1 col mobile / 2 tablet / 4 desktop
  - Gráfico + Atividades: full-width no mobile, [3,2] no desktop
  - Metas: 1 col mobile / 2 tablet / 3 desktop
  - Orçamento: empilhado no mobile
"""

import streamlit as st
import pandas as pd
from datetime import date
from database.queries import (
    get_home_summary, get_cashflow_chart_data, get_today_activities,
    get_goals, get_budget_vs_actual,
)
from components.charts import cashflow_bar_line, gauge_goal, budget_bar_comparison
from components.styles import page_header
from datetime import date as _date
from utils.helpers import fmt_currency, priority_emoji, fmt_date, card_metric
from utils.responsive import kpi_row, is_mobile, get_device


def render():
    page_header(
        "Painel Financeiro",
        f"Resumo do dia — {date.today().strftime('%d/%m/%Y')}",
        "🏠",
    )

    # ─── KPIs responsivos ────────────────────────────────────────────────
    summary = get_home_summary()
    kpi_row([
        dict(label="Contas em Atraso",  value=fmt_currency(summary.get('overdue', 0)),
             delta="⚠️ Vencidas e não pagas",  color="#EF4444", icon="🚨"),
        dict(label="Vencem em 3 dias",  value=fmt_currency(summary.get('due_soon', 0)),
             delta="Atenção ao prazo",         color="#F59E0B", icon="⏳"),
        dict(label="Contas a Receber",  value=fmt_currency(summary.get('receivable', 0)),
             delta="Entradas pendentes",        color="#10B981", icon="📥"),
        dict(label="Saldo do Dia",      value=fmt_currency(summary.get('balance_today', 0)),
             delta="Entradas – Saídas hoje",    color="#3B82F6", icon="💰"),
    ])

    st.markdown("<br>", unsafe_allow_html=True)

    # ─── Gráfico + Atividades ─────────────────────────────────────────────
    if is_mobile():
        _render_chart()
        _render_activities()
    else:
        col_chart, col_act = st.columns([3, 2])
        with col_chart: _render_chart()
        with col_act:   _render_activities()

    st.markdown("---")

    # ─── Metas ────────────────────────────────────────────────────────────
    st.markdown("#### 🎯 Metas em Andamento")
    df_goals     = get_goals()
    active_goals = df_goals[df_goals['status'] == 'Em andamento'] if not df_goals.empty else pd.DataFrame()

    if active_goals.empty:
        st.info("Nenhuma meta ativa. Cadastre suas metas na aba Finanças > Metas.")
    else:
        n_cols = min({'mobile': 1, 'tablet': 2, 'desktop': 3}[get_device()], len(active_goals))
        cols   = st.columns(n_cols)
        for i, (_, goal) in enumerate(active_goals.iterrows()):
            with cols[i % n_cols]:
                target  = float(goal.get('target_value')  or 0)
                current = float(goal.get('current_value') or 0)
                if target > 0:
                    st.plotly_chart(gauge_goal(current, target, goal['title']),
                                    use_container_width=True, config={"displayModeBar": False},
                                    key=f"gauge_{int(goal['id'])}")
                else:
                    st.markdown(f"""
                    <div style="background:#1E293B;border-radius:10px;padding:16px;
                                border:1px solid #334155;margin-bottom:8px">
                        <b style="color:#93C5FD">{goal['title']}</b>
                        <p style="color:#94A3B8;font-size:12px;margin:4px 0">
                            Prazo: {fmt_date(goal.get('time_bound'))}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

    st.markdown("---")

    # ─── Orçamento vs Realizado ───────────────────────────────────────────
    st.markdown("#### 📈 Orçamento vs Realizado — Mês Atual")
    df_bva = get_budget_vs_actual(date.today().replace(day=1))

    if not df_bva.empty and df_bva['planned'].sum() > 0:
        if is_mobile():
            st.plotly_chart(budget_bar_comparison(df_bva),
                            use_container_width=True, config={"displayModeBar": False})
            _render_budget_table(df_bva)
        else:
            c1, c2 = st.columns([2, 1])
            with c1:
                st.plotly_chart(budget_bar_comparison(df_bva),
                                use_container_width=True, config={"displayModeBar": False})
            with c2:
                _render_budget_table(df_bva)
    else:
        st.info("Configure o orçamento em Finanças > Metas e Orçamento.")


# ── helpers internos ──────────────────────────────────────────────────────────

def _render_chart():
    st.markdown("#### 📊 Fluxo de Caixa — Últimos 6 Meses")
    df_cf = get_cashflow_chart_data(6)
    st.plotly_chart(cashflow_bar_line(df_cf),
                    use_container_width=True, config={"displayModeBar": False})


def _render_activities():
    # ── Grid: Atividades · Hábitos · Treino ─────────────────────────────────
    col_act, col_hab, col_gym = st.columns(3)

    # ── Atividades de Hoje ────────────────────────────────────────────────────
    with col_act:
        st.markdown("#### 📋 Atividades de Hoje")
        df_act = get_today_activities()
        if df_act.empty:
            st.markdown('<div style="text-align:center;padding:20px;color:#64748B">'
                        '<div style="font-size:28px">✅</div><p style="font-size:13px">'
                        'Nenhuma atividade hoje!</p></div>', unsafe_allow_html=True)
        else:
            priority_order = {
                'Urgente-Urgente': 1, 'Importante-Urgente': 2,
                'Importante não Urgente': 3, 'Não importante-Não urgente': 4,
            }
            df_act['_order'] = df_act['priority'].map(priority_order)
            for _, row in df_act.sort_values('_order').head(8).iterrows():
                emoji  = priority_emoji(row.get('priority', ''))
                status = row.get('status', '')
                done   = status == 'Concluído'
                st.markdown(
                    f'<div style="background:#1E293B;border-radius:8px;padding:8px 12px;'
                    f'margin-bottom:6px;border:1px solid #334155;'
                    f'opacity:{0.5 if done else 1}">'                    f'<div style="color:#E2E8F0;font-size:13px;font-weight:500">'
                    f'{"✅" if done else emoji} {row["title"]}</div>'                    f'<div style="color:#64748B;font-size:11px">{row.get("priority","")}</div>'                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ── Hábitos de Hoje ───────────────────────────────────────────────────────
    with col_hab:
        st.markdown("#### 🔄 Hábitos de Hoje")
        try:
            from database.queries_habitos import get_today_habits, _is_scheduled
            df_hab = get_today_habits()
            today_h = _date.today()
            hab_today = []
            if not df_hab.empty:
                for _, hr in df_hab.iterrows():
                    if _is_scheduled(today_h, hr.get('frequency_type','Diário'),
                                     hr.get('frequency_days','')):
                        hab_today.append(hr)
            if not hab_today:
                st.markdown('<div style="text-align:center;padding:20px;color:#64748B">'
                            '<div style="font-size:28px">🎯</div><p style="font-size:13px">'
                            'Nenhum hábito hoje!</p></div>', unsafe_allow_html=True)
            else:
                for hr in hab_today[:8]:
                    done_h = bool(hr.get('done_today', False))
                    color  = hr.get('color', '#3B82F6')
                    icon   = hr.get('icon', '🎯')
                    st.markdown(
                        f'<div style="background:#1E293B;border-radius:8px;padding:8px 12px;'
                        f'margin-bottom:6px;border-left:3px solid {color};'
                        f'border:1px solid #334155;opacity:{0.5 if done_h else 1}">'                        f'<span style="font-size:16px">{icon}</span> '                        f'<span style="color:#E2E8F0;font-size:13px">{hr["name"]}</span> '                        f'{"✅" if done_h else ""}'                        f'</div>',
                        unsafe_allow_html=True,
                    )
        except Exception:
            st.info("Configure hábitos na aba Hábitos.")

    # ── Treino de Hoje ────────────────────────────────────────────────────────
    with col_gym:
        st.markdown("#### 🏋️ Treino de Hoje")
        try:
            from database.queries_saude import get_divisions, get_exercises
            DAYS_PT = ['Segunda','Terça','Quarta','Quinta','Sexta','Sábado','Domingo']
            today_name = DAYS_PT[_date.today().weekday()]
            df_divs = get_divisions()
            treino_hoje = None
            if not df_divs.empty:
                # Primeiro tenta match exato, depois match parcial
                for _, div in df_divs.iterrows():
                    dow = str(div.get('day_of_week') or '')
                    if today_name in dow:
                        treino_hoje = div
                        break
                if treino_hoje is None:
                    # Pega o primeiro com "Livre" ou qualquer um
                    free = df_divs[df_divs['day_of_week'].isna() |
                                   df_divs['day_of_week'].str.contains('Livre', na=False)]
                    if not free.empty:
                        treino_hoje = free.iloc[0]
            if treino_hoje is None:
                st.markdown('<div style="text-align:center;padding:20px;color:#64748B">'
                            '<div style="font-size:28px">💪</div><p style="font-size:13px">'
                            'Sem treino cadastrado para hoje.</p></div>', unsafe_allow_html=True)
            else:
                muscles = str(treino_hoje.get('muscle_groups') or '')
                st.markdown(
                    f'<div style="background:#1E293B;border-radius:8px;padding:10px 14px;'
                    f'margin-bottom:8px;border-left:4px solid #10B981;">'                    f'<b style="color:#6EE7B7">{treino_hoje["name"]}</b>'                    f'<div style="color:#64748B;font-size:11px">{muscles}</div></div>',
                    unsafe_allow_html=True,
                )
                df_ex = get_exercises(int(treino_hoje['id']))
                if not df_ex.empty:
                    for _, ex in df_ex.head(8).iterrows():
                        equip = f' · {ex["equipment"]}' if ex.get('equipment') else ''
                        st.markdown(
                            f'<div style="color:#94A3B8;font-size:12px;padding:3px 0 3px 12px;'
                            f'border-left:2px solid #334155">• {ex["name"]}{equip}</div>',
                            unsafe_allow_html=True,
                        )
        except Exception:
            st.info("Configure treinos na aba Saúde.")


def _render_budget_table(df_bva):
    df = df_bva.copy()

    # Sinal: Entrada positivo, Saída negativo
    df['Diferença'] = (df['planned'] - df['actual']) * df['flow_type'].apply(
        lambda t: 1 if t == 'Entrada' else -1
    )
    df['Tipo']   = df['flow_type'].apply(lambda t: "📈 Entrada" if t == 'Entrada' else "📉 Saída")
    df['Status'] = df['Diferença'].apply(lambda x: "✅ Ok" if x >= 0 else "❌ Excedeu")

    # Linha de resultado
    entrada_p = df.loc[df['flow_type']=='Entrada','planned'].sum()
    saida_p   = df.loc[df['flow_type']=='Saída',  'planned'].sum()
    entrada_a = df.loc[df['flow_type']=='Entrada','actual'].sum()
    saida_a   = df.loc[df['flow_type']=='Saída',  'actual'].sum()
    resultado = entrada_a - saida_a
    resultado_p = entrada_p - saida_p

    df_show = df[['Tipo','category','planned','actual','Diferença','Status']].rename(columns={
        'category': 'Categoria', 'planned': 'Orçado (R$)', 'actual': 'Realizado (R$)',
        'Diferença': 'Diferença (R$)',
    })

    # Linha total
    total_row = pd.DataFrame([{
        'Tipo': '💰 RESULTADO',
        'Categoria': '— Entradas − Saídas —',
        'Orçado (R$)': resultado_p,
        'Realizado (R$)': resultado,
        'Diferença (R$)': resultado - resultado_p,
        'Status': "✅ Positivo" if resultado >= 0 else "❌ Negativo",
    }])
    df_show = pd.concat([df_show, total_row], ignore_index=True)

    st.dataframe(
        df_show.style.format({
            'Orçado (R$)':    'R$ {:,.2f}',
            'Realizado (R$)': 'R$ {:,.2f}',
            'Diferença (R$)': 'R$ {:,.2f}',
        }),
        hide_index=True,
        use_container_width=True,
        height=min(600, 40 + len(df_show) * 38),
    )
