"""
components/charts.py
Biblioteca de gráficos Plotly com tema dark — BK Finance
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from utils.helpers import CHART_COLORS


def _base_layout(**extra) -> dict:
    """Retorna layout base sem duplicar chaves de eixo."""
    layout = dict(
        paper_bgcolor=CHART_COLORS["bg"],
        plot_bgcolor=CHART_COLORS["surface"],
        font=dict(color=CHART_COLORS["text"], family="Inter, sans-serif"),
        margin=dict(l=40, r=20, t=50, b=40),
        legend=dict(
            bgcolor="rgba(30,41,59,0.8)",
            bordercolor="#334155",
            borderwidth=1,
        ),
        xaxis=dict(
            gridcolor="#1E293B",
            linecolor="#334155",
            showgrid=True,
            tickfont=dict(color="#94A3B8"),
        ),
        yaxis=dict(
            gridcolor="#1E293B",
            linecolor="#334155",
            showgrid=True,
            tickfont=dict(color="#94A3B8"),
        ),
    )
    layout.update(extra)
    return layout


def cashflow_bar_line(df: pd.DataFrame) -> go.Figure:
    """
    Gráfico de barras + linha para o fluxo de caixa.
    Barras: Entradas (acima do eixo) e Saídas (abaixo).
    Linha: Saldo acumulado (eixo y2).
    """
    if df.empty:
        return _empty_figure("Sem dados de fluxo de caixa")

    months = df['month'].astype(str).tolist()
    acc_col = df.get('accumulated', df.get('balance', [0] * len(months)))

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name="Entradas",
        x=months,
        y=df['income'],
        marker=dict(color=CHART_COLORS["income"], opacity=0.85, line=dict(width=0)),
        hovertemplate="<b>%{x}</b><br>Entrada: R$ %{y:,.2f}<extra></extra>",
        yaxis="y1",
    ))

    fig.add_trace(go.Bar(
        name="Saídas",
        x=months,
        y=[-v for v in df['expense']],
        marker=dict(color=CHART_COLORS["expense"], opacity=0.85, line=dict(width=0)),
        hovertemplate="<b>%{x}</b><br>Saída: R$ %{customdata:,.2f}<extra></extra>",
        customdata=df['expense'],
        yaxis="y1",
    ))

    fig.add_trace(go.Scatter(
        name="Acumulado",
        x=months,
        y=acc_col,
        mode="lines+markers",
        line=dict(color=CHART_COLORS["primary"], width=3),
        marker=dict(size=8, color=CHART_COLORS["primary"], line=dict(color="white", width=2)),
        hovertemplate="<b>%{x}</b><br>Acumulado: R$ %{y:,.2f}<extra></extra>",
        yaxis="y2",
    ))

    fig.update_layout(
        paper_bgcolor=CHART_COLORS["bg"],
        plot_bgcolor=CHART_COLORS["surface"],
        font=dict(color=CHART_COLORS["text"], family="Inter, sans-serif"),
        margin=dict(l=40, r=60, t=60, b=40),
        barmode="overlay",
        title=dict(text="Fluxo de Caixa — Últimos 6 Meses", font=dict(size=16, color="#93C5FD")),
        legend=dict(
            bgcolor="rgba(30,41,59,0.8)",
            bordercolor="#334155",
            borderwidth=1,
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        xaxis=dict(
            gridcolor="#1E293B",
            linecolor="#334155",
            showgrid=True,
            tickfont=dict(color="#94A3B8"),
        ),
        yaxis=dict(
            title="Entradas / Saídas (R$)",
            gridcolor="#1E293B",
            linecolor="#334155",
            showgrid=True,
            tickfont=dict(color="#94A3B8"),
            tickprefix="R$ ",
        ),
        yaxis2=dict(
            title="Acumulado (R$)",
            overlaying="y",
            side="right",
            showgrid=False,
            tickfont=dict(color=CHART_COLORS["primary"]),
            tickprefix="R$ ",
            color=CHART_COLORS["primary"],
        ),
    )
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

    fig.update_layout(**_base_layout(
        title=dict(text=title, font=dict(size=15, color="#93C5FD")),
        barmode="group",
    ))
    return fig


def pie_by_category(df: pd.DataFrame, title: str = "Gastos por Categoria") -> go.Figure:
    """Pizza de distribuição por categoria."""
    if df.empty or 'category' not in df.columns:
        return _empty_figure(title)

    val_col = 'value' if 'value' in df.columns else df.columns[-1]

    fig = go.Figure(go.Pie(
        labels=df['category'],
        values=df[val_col],
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
        legend=dict(bgcolor="rgba(30,41,59,0.8)", bordercolor="#334155", borderwidth=1),
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def budget_bar_comparison(df: pd.DataFrame) -> go.Figure:
    """
    Gráfico de orçamento com sinal:
      - Categorias Entrada → valores positivos (acima do eixo X)
      - Categorias Saída   → valores negativos (abaixo do eixo X)
      - Valores exibidos sobre cada barra
      - Barra extra "Resultado" = total Entradas - total Saídas
    """
    import numpy as np
    if df.empty:
        return _empty_figure("Sem dados de orçamento")

    df = df.copy()

    # Aplica sinal conforme flow_type
    sign = df['flow_type'].apply(lambda t: 1 if t == 'Entrada' else -1)
    df['planned_signed'] = df['planned'] * sign
    df['actual_signed']  = df['actual']  * sign

    # Resultado (linha extra no final)
    total_entrada_p = df.loc[df['flow_type']=='Entrada', 'planned'].sum()
    total_saida_p   = df.loc[df['flow_type']=='Saída',   'planned'].sum()
    total_entrada_a = df.loc[df['flow_type']=='Entrada', 'actual'].sum()
    total_saida_a   = df.loc[df['flow_type']=='Saída',   'actual'].sum()
    result_p = total_entrada_p - total_saida_p
    result_a = total_entrada_a - total_saida_a

    cats      = list(df['category']) + ['💰 Resultado']
    planned_y = list(df['planned_signed']) + [result_p]
    actual_y  = list(df['actual_signed'])  + [result_a]

    # Cores dinâmicas por valor (positivo=verde, negativo=vermelho para resultado)
    def bar_color(vals, base_color, neg_color="#EF4444"):
        return [base_color if v >= 0 else neg_color for v in vals]

    fig = go.Figure()

    # Barra Orçado
    fig.add_trace(go.Bar(
        name="Orçado",
        x=cats,
        y=planned_y,
        marker_color=bar_color(planned_y, CHART_COLORS["planned"]),
        text=[f"R$ {abs(v):,.0f}" for v in planned_y],
        textposition="outside",
        textfont=dict(size=10, color="#94A3B8"),
        hovertemplate="<b>%{x}</b><br>Orçado: R$ %{customdata:,.2f}<extra></extra>",
        customdata=[abs(v) for v in planned_y],
    ))

    # Barra Realizado
    fig.add_trace(go.Bar(
        name="Realizado",
        x=cats,
        y=actual_y,
        marker_color=bar_color(actual_y, CHART_COLORS["actual"]),
        text=[f"R$ {abs(v):,.0f}" for v in actual_y],
        textposition="outside",
        textfont=dict(size=10, color="#F1F5F9"),
        hovertemplate="<b>%{x}</b><br>Realizado: R$ %{customdata:,.2f}<extra></extra>",
        customdata=[abs(v) for v in actual_y],
    ))

    # Linha do zero
    fig.add_hline(y=0, line_color="#475569", line_width=1)

    fig.update_layout(**_base_layout(
        title=dict(
            text="Orçado vs Realizado — Entradas (+) · Saídas (−) · Resultado",
            font=dict(size=14, color="#93C5FD"),
        ),
        barmode="group",
        yaxis=dict(
            tickformat="R$ ,.0f",
            tickprefix="R$ ",
            zeroline=True,
            zerolinecolor="#475569",
            zerolinewidth=1,
        ),
    ))
    # Aumenta height para caber os valores acima das barras
    fig.update_layout(height=420, uniformtext_minsize=8, uniformtext_mode='hide')
    return fig


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


def _empty_figure(msg: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor=CHART_COLORS["bg"],
        plot_bgcolor=CHART_COLORS["surface"],
        font=dict(color=CHART_COLORS["text"]),
        margin=dict(l=40, r=20, t=40, b=40),
        annotations=[dict(
            text=msg, x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="#64748B"), xref="paper", yref="paper",
        )],
    )
    return fig
