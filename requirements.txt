"""
utils/helpers.py
Funções utilitárias gerais
"""

import pandas as pd
import streamlit as st
from datetime import date, datetime
import io
import locale

try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except Exception:
    pass


def fmt_currency(value: float) -> str:
    """Formata valor em Real Brasileiro."""
    try:
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return f"R$ {value:.2f}"


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


def card_metric(label: str, value: str, delta: str = "", color: str = "#60A5FA", icon: str = "💰"):
    """Renderiza card de métrica estilizado."""
    delta_html = f'<p style="color:#94A3B8;font-size:12px;margin:4px 0 0 0">{delta}</p>' if delta else ""
    st.markdown(f"""
    <div style="
        background:linear-gradient(135deg,#1E293B 0%,#0F172A 100%);
        border:1px solid #334155;
        border-left:4px solid {color};
        border-radius:12px;
        padding:16px 20px;
        margin-bottom:8px;
    ">
        <p style="color:#94A3B8;font-size:12px;margin:0;letter-spacing:0.05em;text-transform:uppercase">
            {icon} {label}
        </p>
        <p style="color:{color};font-size:24px;font-weight:700;margin:4px 0 0 0">{value}</p>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


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
