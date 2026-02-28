"""
components/charts.py
Biblioteca de gráficos Plotly com tema dark consistente — BK Finance
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from utils.helpers import CHART_COLORS


LAYOUT_BASE = dict(
    paper_bgcolor=CHART_COLORS["bg"],
    plot_bgcolor=CHART_COLORS["surface"],
    font=dict(color=CHART_COLORS["text"], family="Inter, sans-serif"),
    margin=dict(l=40, r=20, t=40, b=40),
    legend=dict(
        bgcolor="rgba(30,41,59,0.8)",
        bordercolor="#334155",
        borderwidth=1,
    ),
    xaxis=dict(
        gridcolor=CHART_COLORS["grid"],
        linecolor="#334155",
        showgrid=True,
    ),
    yaxis=dict(
        gridcolor=CHART_COLORS["grid"],
        linecolor="#334155",
        showgrid=True,
    ),
)


def cashflow_bar_line(df: pd.DataFrame) -> go.Figure:
    """
    Gráfico de barras + linha para o fluxo de caixa.
    Barras: Entradas (cima) e Saídas (baixo do eixo y).
    Linha: Saldo acumulado.
    """
    if df.empty:
        return _empty_figure("Sem dados de fluxo de caixa")

    months = df['month'].astype(str).tolist()

    fig = go.Figure()

    # Barras de entrada (positivo)
    fig.add_trace(go.Bar(
        name="Entradas",
        x=months,
        y=df['income'],
        marker=dict(
            color=CHART_COLORS["income"],
            opacity=0.85,
            line=dict(width=0),
        ),
        hovertemplate="<b>%{x}</b><br>Entrada: R$ %{y:,.2f}<extra></extra>",
    ))

    # Barras de saída (negativo)
    fig.add_trace(go.Bar(
        name="Saídas",
        x=months,
        y=[-v for v in df['expense']],
        marker=dict(
            color=CHART_COLORS["expense"],
            opacity=0.85,
            line=dict(width=0),
        ),
        hovertemplate="<b>%{x}</b><br>Saída: R$ %{customdata:,.2f}<extra></extra>",
        customdata=df['expense'],
    ))

    # Linha acumulada
    fig.add_trace(go.Scatter(
        name="Acumulado",
        x=months,
        y=df['accumulated'] if 'accumulated' in df.columns else df.get('balance', [0] * len(months)),
        mode="lines+markers",
        line=dict(color=CHART_COLORS["primary"], width=3, dash="solid"),
        marker=dict(size=8, color=CHART_COLORS["primary"], line=dict(color="white", width=2)),
        hovertemplate="<b>%{x}</b><br>Acumulado: R$ %{y:,.2f}<extra></extra>",
        yaxis="y2",
    ))

    layout = {**LAYOUT_BASE}
    layout.update(
        title=dict(text="Fluxo de Caixa — Últimos 6 Meses", font=dict(size=16, color="#93C5FD")),
        barmode="overlay",
        yaxis=dict(**LAYOUT_BASE.get("yaxis", {}), title="Entradas / Saídas (R$)"),
        yaxis2=dict(
            title="Acumulado (R$)",
            overlaying="y",
            side="right",
            gridcolor="transparent",
            showgrid=False,
            color=CHART_COLORS["primary"],
        ),
        legend=dict(**LAYOUT_BASE["legend"], orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_layout(**layout)
    return fig


def income_expense_bar(df: pd.DataFrame, title: str = "Entradas x Saídas") -> go.Figure:
    """Barras agrupadas para previsto/realizado por mês."""
    if df.empty:
        return _empty_figure("Sem dados")

    fig = go.Figure()
    for col, label, color in [
        ('income', 'Entradas', CHART_COLORS["income"]),
        ('expense', 'Saídas', CHART_COLORS["expense"]),
    ]:
        if col in df.columns:
            fig.add_trace(go.Bar(
                name=label,
                x=df['month'].astype(str),
                y=df[col],
                marker_color=color,
                hovertemplate=f"<b>%{{x}}</b><br>{label}: R$ %{{y:,.2f}}<extra></extra>",
            ))

    layout = {**LAYOUT_BASE}
    layout['title'] = dict(text=title, font=dict(size=15, color="#93C5FD"))
    layout['barmode'] = "group"
    fig.update_layout(**layout)
    return fig


def pie_by_category(df: pd.DataFrame, title: str = "Gastos por Categoria") -> go.Figure:
    """Pizza de distribuição por categoria."""
    if df.empty or 'category' not in df.columns:
        return _empty_figure(title)

    fig = go.Figure(go.Pie(
        labels=df['category'],
        values=df['value'] if 'value' in df.columns else df.get('actual', df.iloc[:, 1]),
        hole=0.45,
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent}<extra></extra>",
        marker=dict(
            colors=px.colors.qualitative.Set3,
            line=dict(color=CHART_COLORS["bg"], width=2),
        ),
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color="#93C5FD")),
        paper_bgcolor=CHART_COLORS["bg"],
        font=dict(color=CHART_COLORS["text"]),
        showlegend=True,
        legend=LAYOUT_BASE["legend"],
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def budget_vs_actual_pie(df_budget: pd.DataFrame, df_actual: pd.DataFrame) -> tuple:
    """Retorna dois gráficos de pizza: Previsto e Realizado."""
    fig_p = pie_by_category(
        df_budget.rename(columns={'planned': 'value'}) if not df_budget.empty else pd.DataFrame(),
        title="🎯 Orçamento Previsto por Categoria"
    )
    fig_a = pie_by_category(
        df_actual.rename(columns={'actual': 'value'}) if not df_actual.empty else pd.DataFrame(),
        title="✅ Realizado por Categoria"
    )
    return fig_p, fig_a


def gauge_goal(current: float, target: float, title: str) -> go.Figure:
    """Gauge para progresso de meta."""
    pct = min(current / target * 100, 100) if target > 0 else 0
    color = "#10B981" if pct >= 75 else "#F59E0B" if pct >= 40 else "#EF4444"

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=current,
        delta={"reference": target, "valueformat": ",.0f"},
        title={"text": title, "font": {"size": 14, "color": "#93C5FD"}},
        gauge={
            "axis": {"range": [0, target], "tickformat": ",.0f"},
            "bar": {"color": color, "thickness": 0.3},
            "bgcolor": CHART_COLORS["surface"],
            "bordercolor": "#334155",
            "steps": [
                {"range": [0, target * 0.4], "color": "rgba(239,68,68,0.2)"},
                {"range": [target * 0.4, target * 0.75], "color": "rgba(245,158,11,0.2)"},
                {"range": [target * 0.75, target], "color": "rgba(16,185,129,0.2)"},
            ],
        },
        number={"prefix": "R$ ", "valueformat": ",.2f"},
    ))
    fig.update_layout(
        paper_bgcolor=CHART_COLORS["bg"],
        font=dict(color=CHART_COLORS["text"]),
        margin=dict(l=20, r=20, t=60, b=20),
        height=250,
    )
    return fig


def budget_bar_comparison(df: pd.DataFrame) -> go.Figure:
    """Barras comparando orçado x realizado por categoria."""
    if df.empty:
        return _empty_figure("Sem dados de orçamento")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Orçado",
        x=df['category'],
        y=df['planned'],
        marker_color=CHART_COLORS["planned"],
        hovertemplate="<b>%{x}</b><br>Orçado: R$ %{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Realizado",
        x=df['category'],
        y=df['actual'],
        marker_color=CHART_COLORS["actual"],
        hovertemplate="<b>%{x}</b><br>Realizado: R$ %{y:,.2f}<extra></extra>",
    ))
    layout = {**LAYOUT_BASE}
    layout['title'] = dict(text="Orçado vs Realizado por Categoria", font=dict(size=15, color="#93C5FD"))
    layout['barmode'] = "group"
    fig.update_layout(**layout)
    return fig


def _empty_figure(msg: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        **LAYOUT_BASE,
        annotations=[dict(
            text=msg, x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="#64748B"), xref="paper", yref="paper"
        )],
    )
    return fig
