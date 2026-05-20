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
    st.markdown("#### 📋 Atividades de Hoje")
    df_act = get_today_activities()
    if df_act.empty:
        st.markdown("""
        <div style="text-align:center;padding:32px;color:#64748B">
            <div style="font-size:36px">✅</div>
            <p>Nenhuma atividade vencendo hoje!</p>
        </div>
        """, unsafe_allow_html=True)
        return
    priority_order = {
        'Urgente-Urgente': 1, 'Importante-Urgente': 2,
        'Importante não Urgente': 3, 'Não importante-Não urgente': 4,
    }
    df_act['_order'] = df_act['priority'].map(priority_order)
    for _, row in df_act.sort_values('_order').iterrows():
        emoji  = priority_emoji(row.get('priority', ''))
        is_sub = row.get('parent_id') is not None
        indent = "margin-left:14px;border-left:3px solid #3B82F6;padding-left:10px;" if is_sub else ""
        st.markdown(f"""
        <div style="background:#1E293B;border-radius:8px;padding:10px 14px;
                    margin-bottom:8px;{indent}border:1px solid #334155">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <span style="font-weight:500;color:#E2E8F0">{emoji} {row['title']}</span>
                <span style="font-size:11px;color:#64748B">{row.get('status','')}</span>
            </div>
            <div style="font-size:11px;color:#94A3B8;margin-top:4px">{row.get('priority','')}</div>
        </div>
        """, unsafe_allow_html=True)


def _render_budget_table(df_bva):
    df = df_bva.copy()
    df['Diferença'] = df['planned'] - df['actual']
    df['Status']    = df['Diferença'].apply(lambda x: "✅ Ok" if x >= 0 else "❌ Excedeu")
    st.dataframe(
        df[['category', 'planned', 'actual', 'Diferença', 'Status']].rename(columns={
            'category': 'Categoria', 'planned': 'Orçado', 'actual': 'Realizado',
        }).style.format({'Orçado': 'R$ {:,.2f}', 'Realizado': 'R$ {:,.2f}', 'Diferença': 'R$ {:,.2f}'}),
        hide_index=True, use_container_width=True,
    )
