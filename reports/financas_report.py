"""
reports/financas_report.py
Relatório em Word do módulo Finanças: saldos, fluxo de caixa dos últimos
meses, pendências (a pagar/a receber, com vencidas destacadas), maiores
categorias de despesa e extrato resumido do período.
"""

from datetime import date

from database.queries import (
    get_home_summary, get_cashflow_chart_data, get_all_bank_balances,
    get_transactions,
)
from reports.builder import ReportBuilder, apply_chart_style, fmt_brl, fmt_date, CHART, nz


def build_financas_report(user_id: int, username: str, months: int = 6) -> "io.BytesIO":
    today = date.today()
    summary = get_home_summary(user_id)
    df_cf = get_cashflow_chart_data(user_id, months=months)
    df_banks = get_all_bank_balances(user_id)
    df_pending = get_transactions(user_id, status="Não pago")

    total_current = float(df_banks["current_balance"].sum()) if df_banks is not None and not df_banks.empty else 0.0

    a_pagar = a_receber = vencido = 0.0
    if df_pending is not None and not df_pending.empty:
        saida = df_pending[df_pending["flow_type"] == "Saída"]
        entrada = df_pending[df_pending["flow_type"] == "Entrada"]
        a_pagar = float(saida["total_value"].sum())
        a_receber = float(entrada["total_value"].sum())
        overdue_mask = saida["due_date"].apply(lambda d: (d.date() if hasattr(d, "date") else d) < today)
        vencido = float(saida[overdue_mask]["total_value"].sum()) if not saida.empty else 0.0

    rb = ReportBuilder(
        report_title="Relatório Financeiro",
        report_subtitle=f"Saldos, fluxo de caixa e pendências — últimos {months} meses",
        username=username,
        icon="💼",
    )

    rb.kpi_row([
        ("Saldo atual (bancos)", fmt_brl(total_current), "primary"),
        ("A pagar", fmt_brl(a_pagar), "warning"),
        ("A receber", fmt_brl(a_receber), "success"),
        ("Vencido", fmt_brl(vencido), "danger" if vencido > 0 else "success"),
    ])

    if vencido > 0:
        rb.callout(
            f"Você tem {fmt_brl(vencido)} em contas vencidas e não pagas. Regularize o quanto antes para evitar juros e multas.",
            tone="danger", icon="⚠️",
        )

    rb.section_title("Fluxo de caixa", "📈")
    if df_cf is not None and not df_cf.empty:
        apply_chart_style()
        _cashflow_chart(rb, df_cf)
    else:
        rb.empty_state("Sem movimentações pagas no período para compor o fluxo de caixa.")

    rb.section_title("Saldos bancários", "🏦")
    if df_banks is not None and not df_banks.empty:
        rows = [
            [b["name"], nz(b.get("account")) or "—", fmt_brl(b["initial_balance"]), fmt_brl(b["current_balance"])]
            for _, b in df_banks.iterrows()
        ]
        rb.table(
            headers=["Banco", "Conta", "Saldo inicial", "Saldo atual"],
            rows=rows,
            col_widths=[6.0, 4.2, 3.5, 3.5],
            align=["left", "left", "right", "right"],
        )
        rb.paragraph(f"Saldo total: {fmt_brl(total_current)}", bold=True, size=10)
    else:
        rb.empty_state("Nenhum banco cadastrado.")

    rb.section_title("Pendências", "⏰")
    if df_pending is not None and not df_pending.empty:
        _pending_table(rb, df_pending, today)
    else:
        rb.empty_state("Nenhuma pendência — tudo pago!")

    rb.section_title("Maiores categorias de despesa (período)", "🏷️")
    df_period = get_transactions(
        user_id,
        start_date=df_cf["month"].min() if df_cf is not None and not df_cf.empty else today.replace(day=1),
        end_date=today,
        status="Pago", flow_type="Saída",
    )
    if df_period is not None and not df_period.empty:
        apply_chart_style()
        _top_categories_chart(rb, df_period)
    else:
        rb.empty_state("Sem despesas pagas no período.")

    rb.section_title("Extrato do período (amostra)", "🧾")
    _extract_table(rb, user_id, df_cf, today)

    return rb.to_bytes()


def _cashflow_chart(rb, df_cf):
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, ax = plt.subplots(figsize=(9.5, 4.0))
    months = df_cf["month"]
    x = range(len(months))
    labels = [m.strftime("%b/%y") if hasattr(m, "strftime") else str(m) for m in months]

    width = 0.38
    ax.bar([i - width / 2 for i in x], df_cf["income"], width=width, color=CHART["success"], label="Entradas", zorder=3)
    ax.bar([i + width / 2 for i in x], df_cf["expense"], width=width, color=CHART["danger"], label="Saídas", zorder=3)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=9)
    ax.grid(axis="y", linestyle="--", alpha=0.5, zorder=0)

    ax2 = ax.twinx()
    ax2.plot(list(x), df_cf["accumulated"], color=CHART["primary"], marker="o", linewidth=2, label="Acumulado")
    ax2.set_yticks([])
    ax2.spines["right"].set_visible(False)

    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=8.5, frameon=False)
    fig.tight_layout()
    rb.chart_image(fig)


def _top_categories_chart(rb, df_period):
    import matplotlib.pyplot as plt

    agg = df_period.groupby("category_name")["total_value"].sum().sort_values(ascending=False).head(8)
    if agg.empty:
        rb.empty_state("Sem dados de categoria.")
        return
    fig, ax = plt.subplots(figsize=(9.5, max(2.2, 0.5 * len(agg) + 0.8)))
    y_pos = range(len(agg))
    ax.barh(y_pos, agg.values, color=CHART["danger"], height=0.55, zorder=3)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels([str(c) for c in agg.index], fontsize=9)
    ax.invert_yaxis()
    ax.grid(axis="x", linestyle="--", alpha=0.5, zorder=0)
    for i, v in enumerate(agg.values):
        ax.text(v, i, f"  {fmt_brl(v)}", va="center", fontsize=8.3, color=CHART["text"])
    fig.tight_layout()
    rb.chart_image(fig)


def _pending_table(rb, df_pending, today):
    rows = []
    row_tones = {}
    df_sorted = df_pending.sort_values("due_date")
    for i, (_, r) in enumerate(df_sorted.iterrows()):
        due = r["due_date"]
        due_d = due.date() if hasattr(due, "date") else due
        overdue = due_d < today
        rows.append([
            "Receber" if r["flow_type"] == "Entrada" else "Pagar",
            nz(r.get("supplier_name")) or nz(r.get("description")) or "—",
            nz(r.get("category_name")) or "—",
            fmt_date(due),
            fmt_brl(r["total_value"]),
        ])
        if overdue:
            row_tones[i] = "danger"
    rb.table(
        headers=["Tipo", "Quem/Descrição", "Categoria", "Vencimento", "Valor"],
        rows=rows[:40],
        col_widths=[2.2, 5.5, 4.0, 2.7, 2.8],
        align=["left", "left", "left", "center", "right"],
        row_tones=row_tones,
    )
    if len(rows) > 40:
        rb.paragraph(f"Mostrando 40 de {len(rows)} pendências (ordenadas por vencimento).", muted=True, size=8.8, italic=True)


def _extract_table(rb, user_id, df_cf, today):
    start = df_cf["month"].min() if df_cf is not None and not df_cf.empty else today.replace(day=1)
    df = get_transactions(user_id, start_date=start, end_date=today, status="Pago")
    if df is None or df.empty:
        rb.empty_state("Sem movimentações pagas no período.")
        return
    df = df.sort_values("due_date", ascending=False).head(30)
    rows = [
        [fmt_date(r["due_date"]), r["flow_type"], nz(r.get("category_name")) or "—",
         nz(r.get("description")) or "—", fmt_brl(r["total_value"])]
        for _, r in df.iterrows()
    ]
    rb.table(
        headers=["Data", "Tipo", "Categoria", "Descrição", "Valor"],
        rows=rows,
        col_widths=[2.5, 2.2, 3.8, 5.7, 3.0],
        align=["center", "center", "left", "left", "right"],
    )
    rb.paragraph("Amostra das 30 movimentações pagas mais recentes do período.", muted=True, size=8.8, italic=True)
