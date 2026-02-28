"""
pages/home.py
Página Home — Painel de Controle BK Finance
"""

import streamlit as st
import pandas as pd
from datetime import date
from database.queries import (
    get_home_summary, get_cashflow_chart_data, get_today_activities,
    get_goals, get_budget_vs_actual
)
from components.charts import cashflow_bar_line, gauge_goal, budget_bar_comparison
from components.styles import page_header
from utils.helpers import fmt_currency, priority_emoji, fmt_date, card_metric


def render():
    page_header(
        "Painel Financeiro",
        f"Resumo do dia — {date.today().strftime('%d/%m/%Y')}",
        "🏠"
    )

    # ─── KPIs do dia ────────────────────────────────────────────────────
    summary = get_home_summary()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        card_metric(
            "Contas em Atraso",
            fmt_currency(summary.get('overdue', 0)),
            "⚠️ Vencidas e não pagas",
            color="#EF4444",
            icon="🚨",
        )
    with c2:
        card_metric(
            "Vencem em 3 dias",
            fmt_currency(summary.get('due_soon', 0)),
            "Atenção ao prazo",
            color="#F59E0B",
            icon="⏳",
        )
    with c3:
        card_metric(
            "Contas a Receber",
            fmt_currency(summary.get('receivable', 0)),
            "Entradas pendentes",
            color="#10B981",
            icon="📥",
        )
    with c4:
        card_metric(
            "Saldo do Dia",
            fmt_currency(summary.get('balance_today', 0)),
            "Entradas – Saídas hoje",
            color="#3B82F6",
            icon="💰",
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ─── Gráfico Fluxo de Caixa ──────────────────────────────────────────
    col_chart, col_act = st.columns([3, 2])

    with col_chart:
        st.markdown("#### 📊 Fluxo de Caixa — Últimos 6 Meses")
        df_cf = get_cashflow_chart_data(6)
        fig = cashflow_bar_line(df_cf)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ─── Atividades do dia ───────────────────────────────────────────────
    with col_act:
        st.markdown("#### 📋 Atividades de Hoje")
        df_act = get_today_activities()

        if df_act.empty:
            st.markdown("""
            <div style="text-align:center;padding:40px;color:#64748B">
                <div style="font-size:36px">✅</div>
                <p>Nenhuma atividade vencendo hoje!</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            priority_order = {
                'Urgente-Urgente': 1,
                'Importante-Urgente': 2,
                'Importante não Urgente': 3,
                'Não importante-Não urgente': 4,
            }
            df_act['_order'] = df_act['priority'].map(priority_order)
            df_act = df_act.sort_values('_order')

            for _, row in df_act.iterrows():
                emoji = priority_emoji(row.get('priority', ''))
                is_sub = row.get('parent_id') is not None
                indent = "margin-left:20px;border-left:3px solid #3B82F6;padding-left:12px;" if is_sub else ""
                st.markdown(f"""
                <div style="background:#1E293B;border-radius:8px;padding:10px 14px;
                            margin-bottom:8px;{indent}
                            border:1px solid #334155">
                    <div style="display:flex;justify-content:space-between;align-items:center">
                        <span style="font-weight:500;color:#E2E8F0">
                            {emoji} {row['title']}
                        </span>
                        <span style="font-size:11px;color:#64748B">{row.get('status','')}</span>
                    </div>
                    <div style="font-size:11px;color:#94A3B8;margin-top:4px">
                        {row.get('priority','')}
                    </div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("---")

    # ─── Metas SMART ────────────────────────────────────────────────────
    st.markdown("#### 🎯 Metas em Andamento")
    df_goals = get_goals()
    active_goals = df_goals[df_goals['status'] == 'Em andamento'] if not df_goals.empty else pd.DataFrame()

    if active_goals.empty:
        st.info("Nenhuma meta ativa. Cadastre suas metas na aba Finanças > Metas.")
    else:
        cols = st.columns(min(len(active_goals), 3))
        for i, (_, goal) in enumerate(active_goals.iterrows()):
            with cols[i % 3]:
                target = float(goal.get('target_value') or 0)
                current = float(goal.get('current_value') or 0)
                if target > 0:
                    fig_gauge = gauge_goal(current, target, goal['title'])
                    st.plotly_chart(fig_gauge, use_container_width=True, config={"displayModeBar": False})
                else:
                    pct = 0
                    deadline = fmt_date(goal.get('time_bound'))
                    st.markdown(f"""
                    <div style="background:#1E293B;border-radius:10px;padding:16px;
                                border:1px solid #334155;margin-bottom:8px">
                        <b style="color:#93C5FD">{goal['title']}</b>
                        <p style="color:#94A3B8;font-size:12px;margin:4px 0">
                            Prazo: {deadline}
                        </p>
                        <div style="background:#0F172A;border-radius:4px;height:6px;margin-top:8px">
                            <div style="width:{pct}%;background:#3B82F6;height:100%;border-radius:4px"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

    st.markdown("---")

    # ─── Orçamento vs Realizado (mês atual) ──────────────────────────────
    st.markdown("#### 📈 Orçamento vs Realizado — Mês Atual")
    today_month = date.today().replace(day=1)
    df_bva = get_budget_vs_actual(today_month)

    if not df_bva.empty and df_bva['planned'].sum() > 0:
        col_pie, col_bar = st.columns([1, 2])
        with col_bar:
            from components.charts import budget_bar_comparison
            fig_bar = budget_bar_comparison(df_bva)
            st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

        with col_pie:
            df_display = df_bva.copy()
            df_display['Diferença'] = df_display['planned'] - df_display['actual']
            df_display['Status'] = df_display['Diferença'].apply(
                lambda x: "✅ Ok" if x >= 0 else "❌ Excedeu"
            )
            st.dataframe(
                df_display[['category', 'planned', 'actual', 'Diferença', 'Status']].rename(columns={
                    'category': 'Categoria', 'planned': 'Orçado', 'actual': 'Realizado'
                }).style.format({'Orçado': 'R$ {:,.2f}', 'Realizado': 'R$ {:,.2f}', 'Diferença': 'R$ {:,.2f}'}),
                hide_index=True,
                use_container_width=True,
            )
    else:
        st.info("Configure o orçamento mensal na aba Finanças > Metas e Orçamento.")
