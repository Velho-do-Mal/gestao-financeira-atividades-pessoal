"""
pages/home.py
Painel de Controle — BK Gestão Pessoal

Layout v3:
  - Fluxo de caixa: largura total
  - Atividades / Hábitos / Treino: 3 colunas abaixo do gráfico (não dentro dele)
  - Orçamento: gráfico largura total → tabela largura total abaixo
  - Lógica de status do orçamento corrigida (Entrada ≠ Saída)
"""

import streamlit as st
import pandas as pd
from datetime import date as _date
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
        "Painel",
        f"Resumo do dia — {_date.today().strftime('%d/%m/%Y')}",
        "🏠",
    )

    # ── KPIs ──────────────────────────────────────────────────────────────
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

    # ── Fluxo de Caixa — LARGURA TOTAL ────────────────────────────────────
    st.markdown("#### 📊 Fluxo de Caixa — Últimos 6 Meses")
    df_cf = get_cashflow_chart_data(6)
    st.plotly_chart(cashflow_bar_line(df_cf),
                    use_container_width=True, config={"displayModeBar": False})

    st.markdown("---")

    # ── Resumo do Dia — 3 colunas LARGURA TOTAL ───────────────────────────
    st.markdown("#### 📅 Resumo do Dia")
    col_act, col_hab, col_gym = st.columns(3)
    with col_act: _section_atividades()
    with col_hab: _section_habitos()
    with col_gym: _section_treino()

    st.markdown("---")

    # ── Metas ────────────────────────────────────────────────────────────
    st.markdown("#### 🎯 Metas em Andamento")
    df_goals     = get_goals()
    active_goals = df_goals[df_goals['status'] == 'Em andamento'] if not df_goals.empty else pd.DataFrame()

    if active_goals.empty:
        st.info("Nenhuma meta ativa. Cadastre em Finanças → Metas.")
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

    # ── Orçamento: gráfico LARGURA TOTAL → tabela LARGURA TOTAL ──────────
    st.markdown("#### 📈 Orçamento vs Realizado — Mês Atual")
    df_bva = get_budget_vs_actual(_date.today().replace(day=1))

    if not df_bva.empty and df_bva['planned'].sum() > 0:
        st.plotly_chart(budget_bar_comparison(df_bva),
                        use_container_width=True, config={"displayModeBar": False},
                        key="budget_chart")
        st.markdown("##### Detalhamento por Categoria")
        _render_budget_table(df_bva)
    else:
        st.info("Configure o orçamento em Finanças → Metas e Orçamento.")


# ── Seções do Resumo do Dia ───────────────────────────────────────────────────

def _section_atividades():
    st.markdown("**📋 Atividades de Hoje**")
    df_act = get_today_activities()
    if df_act.empty:
        st.markdown(
            '<div style="text-align:center;padding:16px;color:#475569">'
            '<div style="font-size:24px">✅</div>'
            '<p style="font-size:12px;margin:4px 0">Sem atividades hoje</p></div>',
            unsafe_allow_html=True)
        return
    priority_order = {
        'Urgente-Urgente': 1, 'Importante-Urgente': 2,
        'Importante não Urgente': 3, 'Não importante-Não urgente': 4,
    }
    df_act['_ord'] = df_act['priority'].map(priority_order).fillna(5)
    for _, row in df_act.sort_values('_ord').head(8).iterrows():
        done  = row.get('status') == 'Concluído'
        emoji = priority_emoji(row.get('priority', ''))
        st.markdown(
            f'<div style="background:#1E293B;border-radius:7px;padding:7px 10px;'
            f'margin-bottom:5px;border:1px solid #334155;opacity:{0.45 if done else 1}">'
            f'<div style="color:#E2E8F0;font-size:12px;font-weight:500">'
            f'{"✅" if done else emoji} {row["title"]}</div>'
            f'<div style="color:#64748B;font-size:10px">{row.get("priority","")}</div>'
            f'</div>',
            unsafe_allow_html=True)


def _section_habitos():
    st.markdown("**🔄 Hábitos de Hoje**")
    try:
        from database.queries_habitos import get_today_habits, _is_scheduled
        today = _date.today()
        df_hab = get_today_habits()
        hab_list = []
        if not df_hab.empty:
            for _, hr in df_hab.iterrows():
                if _is_scheduled(today, hr.get('frequency_type', 'Diário'),
                                  hr.get('frequency_days', '')):
                    hab_list.append(hr)
        if not hab_list:
            st.markdown(
                '<div style="text-align:center;padding:16px;color:#475569">'
                '<div style="font-size:24px">🎯</div>'
                '<p style="font-size:12px;margin:4px 0">Nenhum hábito hoje</p></div>',
                unsafe_allow_html=True)
            return
        for hr in hab_list[:8]:
            done  = bool(hr.get('done_today', False))
            color = hr.get('color', '#3B82F6')
            icon  = hr.get('icon', '🎯')
            st.markdown(
                f'<div style="background:#1E293B;border-radius:7px;padding:7px 10px;'
                f'margin-bottom:5px;border-left:3px solid {color};border:1px solid #334155;'
                f'opacity:{0.45 if done else 1}">'
                f'<span style="font-size:14px">{icon}</span> '
                f'<span style="color:#E2E8F0;font-size:12px">{hr["name"]}</span>'
                f'{"  ✅" if done else ""}'
                f'</div>',
                unsafe_allow_html=True)
    except Exception:
        st.info("Configure hábitos na aba Hábitos.")


def _section_treino():
    st.markdown("**🏋️ Treino de Hoje**")
    try:
        from database.queries_saude import get_divisions, get_exercises
        DAYS_PT = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        today_name = DAYS_PT[_date.today().weekday()]
        df_divs = get_divisions()
        treino = None
        if not df_divs.empty:
            for _, div in df_divs.iterrows():
                if today_name in str(div.get('day_of_week') or ''):
                    treino = div; break
            if treino is None:
                free = df_divs[
                    df_divs['day_of_week'].isna() |
                    df_divs['day_of_week'].str.contains('Livre', na=False)
                ]
                if not free.empty:
                    treino = free.iloc[0]
        if treino is None:
            st.markdown(
                '<div style="text-align:center;padding:16px;color:#475569">'
                '<div style="font-size:24px">💪</div>'
                f'<p style="font-size:12px;margin:4px 0">Sem treino para {today_name}</p></div>',
                unsafe_allow_html=True)
            return
        muscles = str(treino.get('muscle_groups') or '')
        st.markdown(
            f'<div style="background:#1E293B;border-radius:7px;padding:8px 10px;'
            f'margin-bottom:6px;border-left:4px solid #10B981;border:1px solid #334155">'
            f'<b style="color:#6EE7B7;font-size:12px">{treino["name"]}</b>'
            f'<div style="color:#64748B;font-size:10px">{muscles}</div></div>',
            unsafe_allow_html=True)
        df_ex = get_exercises(int(treino['id']))
        if not df_ex.empty:
            for _, ex in df_ex.head(8).iterrows():
                equip = f' · {ex["equipment"]}' if ex.get('equipment') else ''
                st.markdown(
                    f'<div style="color:#94A3B8;font-size:11px;padding:2px 0 2px 10px;'
                    f'border-left:2px solid #334155">• {ex["name"]}{equip}</div>',
                    unsafe_allow_html=True)
    except Exception:
        st.info("Configure treinos na aba Saúde.")


# ── Tabela de Orçamento ───────────────────────────────────────────────────────

def _render_budget_table(df_bva):
    """
    Lógica de status:
      Entrada: realizado >= planejado → ✅ (ganhou mais ou igual)
               realizado <  planejado → ⚠️ (ganhou menos)
      Saída:   realizado <= planejado → ✅ (gastou dentro do orçado)
               realizado >  planejado → ❌ (excedeu o orçado)
      Resultado: Entradas - Saídas
               positivo → ✅ saldo positivo
               negativo → ❌ gastou mais do que ganhou
    """
    df = df_bva.copy()

    df['Tipo'] = df['flow_type'].apply(
        lambda t: "📈 Entrada" if t == 'Entrada' else "📉 Saída"
    )

    def calc_diff(row):
        """Diferença com sinal positivo = bom para ambos os tipos."""
        if row['flow_type'] == 'Entrada':
            return row['actual'] - row['planned']   # + = ganhou mais (bom)
        else:
            return row['planned'] - row['actual']   # + = economizou (bom)

    def calc_status(row):
        if row['flow_type'] == 'Entrada':
            if row['actual'] >= row['planned']:
                return "✅ Meta atingida"
            return "⚠️ Abaixo da meta"
        else:
            if row['actual'] <= row['planned']:
                return "✅ Dentro do orçado"
            return "❌ Excedeu orçado"

    df['Diferença (R$)'] = df.apply(calc_diff, axis=1)
    df['Status']         = df.apply(calc_status, axis=1)

    df_show = df[['Tipo', 'category', 'planned', 'actual', 'Diferença (R$)', 'Status']].rename(
        columns={'category': 'Categoria', 'planned': 'Orçado (R$)', 'actual': 'Realizado (R$)'}
    )

    # Linha de resultado
    ent_p = df.loc[df['flow_type'] == 'Entrada', 'planned'].sum()
    sai_p = df.loc[df['flow_type'] == 'Saída',   'planned'].sum()
    ent_a = df.loc[df['flow_type'] == 'Entrada', 'actual'].sum()
    sai_a = df.loc[df['flow_type'] == 'Saída',   'actual'].sum()
    res_p = ent_p - sai_p
    res_a = ent_a - sai_a

    total_row = pd.DataFrame([{
        'Tipo':           '💰 RESULTADO',
        'Categoria':      'Entradas − Saídas',
        'Orçado (R$)':    res_p,
        'Realizado (R$)': res_a,
        'Diferença (R$)': res_a - res_p,
        'Status': "✅ Saldo positivo" if res_a >= 0 else "❌ Saldo negativo — gastou mais do que ganhou",
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
        height=min(700, 48 + len(df_show) * 40),
    )
