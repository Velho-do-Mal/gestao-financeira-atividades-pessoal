"""
utils/helpers.py
Funções utilitárias gerais
"""

import pandas as pd
from datetime import date, datetime
import io
import locale

try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except Exception:
    pass


def fmt_currency(value: float) -> str:
    """
    Formata valor em Real Brasileiro. Negativo vem com o sinal de menos
    NA FRENTE de tudo (-R$ 1.234,56), não entre o "R$" e o número.
    """
    try:
        value = float(value or 0)
    except (TypeError, ValueError):
        value = 0.0
    sign = "-" if value < 0 else ""
    try:
        body = f"{abs(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{sign}R$ {body}"
    except Exception:
        return f"{sign}R$ {abs(value):.2f}"


def money_html(value, bold: bool = False, highlight_positive: bool = False):
    """
    Retorna o valor formatado em R$ dentro de um <span>, já com a classe
    CSS que pinta de vermelho quando negativo (usar em todos os quadros/
    tabelas em vez de aplicar cor "na mão" em cada template).
    Uso no Jinja: {{ money(valor) }}  (registrado como global, não filtro,
    porque devolve HTML).
    highlight_positive=True também pinta de verde quando >= 0 — usar só
    em KPIs de resultado/saldo onde isso já era o padrão visual.
    """
    from markupsafe import Markup, escape
    try:
        v = float(value or 0)
    except (TypeError, ValueError):
        v = 0.0
    if v < 0:
        css_class = "money money--neg"
    elif highlight_positive:
        css_class = "money money--pos"
    else:
        css_class = "money"
    if bold:
        css_class += " money--bold"
    return Markup(f'<span class="{css_class}">{escape(fmt_currency(v))}</span>')


def fmt_date(d) -> str:
    """Formata data em DD/MM/YYYY."""
    if d is None:
        return ""
    if isinstance(d, (datetime, date)):
        return d.strftime("%d/%m/%Y")
    return str(d)


def priority_color(priority: str) -> str:
    colors = {
        "Urgente-Urgente": "#EF4444",
        "Importante-Urgente": "#F97316",
        "Importante não Urgente": "#EAB308",
        "Não importante-Não urgente": "#22C55E",
    }
    return colors.get(priority, "#94A3B8")


def priority_emoji(priority: str) -> str:
    emojis = {
        "Urgente-Urgente": "🔴",
        "Importante-Urgente": "🟠",
        "Importante não Urgente": "🟡",
        "Não importante-Não urgente": "🟢",
    }
    return emojis.get(priority, "⚪")


def status_icon(status: str, end_date=None) -> str:
    today = date.today()
    if status == "Concluído":
        return "🟢"
    if end_date:
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        if end_date < today:
            return "🔴"
        if (end_date - today).days <= 1:
            return "🟡"
    return "⚪"


def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    """Converte DataFrame para bytes Excel."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Dados')
        workbook = writer.book
        worksheet = writer.sheets['Dados']
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#1E40AF', 'font_color': 'white',
            'border': 1, 'align': 'center'
        })
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_fmt)
        worksheet.set_column(0, len(df.columns) - 1, 18)
    return output.getvalue()


def month_range(n_months: int = 24):
    """Gera lista de datas (primeiro dia do mês) dos próximos N meses."""
    from dateutil.relativedelta import relativedelta
    today = date.today().replace(day=1)
    return [today + relativedelta(months=i) for i in range(n_months)]


CHART_COLORS = {
    "primary": "#3B82F6",
    "success": "#10B981",
    "danger": "#EF4444",
    "warning": "#F59E0B",
    "info": "#8B5CF6",
    "muted": "#64748B",
    "income": "#10B981",
    "expense": "#EF4444",
    "planned": "#3B82F6",
    "actual": "#F59E0B",
    "bg": "#0F172A",
    "surface": "#1E293B",
    "text": "#F1F5F9",
    "grid": "#1E293B",
}
