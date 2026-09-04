"""
reports/saude_nutricao_report.py
Relatório em Word do dia alimentar: macros consumidos x metas, e o
detalhamento refeição a refeição com os alimentos e quantidades.
"""

from datetime import date

from database.queries_saude import get_meals, get_meal_items, get_daily_totals, get_macro_goals
from reports.builder import ReportBuilder, apply_chart_style, fmt_date, CHART, nz


def build_nutricao_report(user_id: int, username: str, meal_date: date = None) -> "io.BytesIO":
    meal_date = meal_date or date.today()

    df_meals = get_meals(user_id, meal_date)
    meals = df_meals.to_dict("records") if df_meals is not None and not df_meals.empty else []
    for m in meals:
        df_items = get_meal_items(user_id, m["id"])
        m["food_items"] = df_items.to_dict("records") if df_items is not None and not df_items.empty else []
        m["kcal"] = sum(float(i["item_kcal"] or 0) for i in m["food_items"])

    totals = get_daily_totals(user_id, meal_date)
    goals = get_macro_goals(user_id)

    rb = ReportBuilder(
        report_title="Relatório de Nutrição",
        report_subtitle=f"Macros e refeições do dia {fmt_date(meal_date)}",
        username=username,
        icon="🍽️",
    )

    kcal_pct = (totals["total_kcal"] / goals["goal_kcal"] * 100) if goals.get("goal_kcal") else 0
    rb.kpi_row([
        ("Calorias", f"{totals['total_kcal']:.0f} / {goals['goal_kcal']:.0f} kcal", "primary"),
        ("Proteína", f"{totals['total_protein']:.0f} / {goals['protein_g']:.0f} g", "success"),
        ("Carboidrato", f"{totals['total_carbs']:.0f} / {goals['carbs_g']:.0f} g", "warning"),
        ("Gordura", f"{totals['total_fat']:.0f} / {goals['fat_g']:.0f} g", "info"),
    ])

    if not meals:
        rb.empty_state(f"Nenhuma refeição registrada em {fmt_date(meal_date)}.")
        return rb.to_bytes()

    rb.section_title("Macros consumidos x meta", "📊")
    apply_chart_style()
    _macro_chart(rb, totals, goals)

    rb.section_title("Refeições do dia", "🍽️")
    for m in meals:
        header = m["name"] + (f"  ·  {nz(m.get('meal_time'))}" if nz(m.get("meal_time")) else "")
        rb.subsection_title(f"{header}  —  {m['kcal']:.0f} kcal")
        if m["food_items"]:
            rows = [
                [it["food_name"], f"{it['quantity_g']:.0f} g", f"{it['item_protein']:.1f} g",
                 f"{it['item_carbs']:.1f} g", f"{it['item_fat']:.1f} g", f"{it['item_kcal']:.0f}"]
                for it in m["food_items"]
            ]
            rb.table(
                headers=["Alimento", "Qtd.", "Proteína", "Carbo", "Gordura", "Kcal"],
                rows=rows,
                col_widths=[6.0, 2.2, 2.5, 2.5, 2.5, 1.5],
                align=["left", "center", "center", "center", "center", "center"],
            )
        else:
            rb.paragraph("Sem itens registrados nesta refeição.", muted=True, size=9.5, italic=True)
        if nz(m.get("notes")):
            rb.paragraph(f"Obs.: {m['notes']}", muted=True, size=9, italic=True)

    return rb.to_bytes()


def _macro_chart(rb, totals, goals):
    import matplotlib.pyplot as plt

    labels = ["Proteína", "Carboidrato", "Gordura"]
    consumed = [totals["total_protein"], totals["total_carbs"], totals["total_fat"]]
    target = [goals.get("protein_g", 0), goals.get("carbs_g", 0), goals.get("fat_g", 0)]
    colors = [CHART["success"], CHART["warning"], CHART["info"]]

    fig, ax = plt.subplots(figsize=(9.0, 3.2))
    x = range(len(labels))
    width = 0.35
    ax.bar([i - width / 2 for i in x], consumed, width=width, color=colors, label="Consumido", zorder=3)
    ax.bar([i + width / 2 for i in x], target, width=width, color=CHART["grid"], label="Meta", zorder=3)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=9.5)
    ax.set_ylabel("gramas", fontsize=9)
    ax.grid(axis="y", linestyle="--", alpha=0.5, zorder=0)
    ax.legend(fontsize=8.5, frameon=False)
    for i, v in enumerate(consumed):
        ax.text(i - width / 2, v, f"{v:.0f}", ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    rb.chart_image(fig, width_cm=15.5)
