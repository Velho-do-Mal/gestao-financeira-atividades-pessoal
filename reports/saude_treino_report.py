"""
reports/saude_treino_report.py
Ficha de treino em Word: divisões, exercícios com séries planejadas
(reps/carga) prontos para levar para a academia, e evolução de carga dos
exercícios com histórico registrado.
"""

from database.queries_saude import get_divisions, get_exercises, get_exercise_sets, get_weight_history
from reports.builder import ReportBuilder, apply_chart_style, CHART, nz


def build_treino_report(user_id: int, username: str) -> "io.BytesIO":
    df_div = get_divisions(user_id)
    divisions = df_div.to_dict("records") if df_div is not None and not df_div.empty else []

    rb = ReportBuilder(
        report_title="Ficha de Treino",
        report_subtitle="Divisões, exercícios, séries planejadas e evolução de carga",
        username=username,
        icon="🏋️",
    )

    if not divisions:
        rb.empty_state("Nenhuma divisão de treino cadastrada ainda.")
        return rb.to_bytes()

    total_exercises = 0
    total_sets = 0
    division_payload = []
    for div in divisions:
        df_ex = get_exercises(user_id, div["id"])
        exercises = df_ex.to_dict("records") if df_ex is not None and not df_ex.empty else []
        for ex in exercises:
            df_sets = get_exercise_sets(user_id, ex["id"])
            ex["sets"] = df_sets.to_dict("records") if df_sets is not None and not df_sets.empty else []
            total_sets += len(ex["sets"])
        total_exercises += len(exercises)
        division_payload.append((div, exercises))

    rb.kpi_row([
        ("Divisões de treino", len(divisions), "primary"),
        ("Exercícios cadastrados", total_exercises, "info"),
        ("Séries planejadas", total_sets, "success"),
    ])

    rb.section_title("Ficha por divisão", "📋")
    for div, exercises in division_payload:
        title = div["name"]
        extra = " · ".join(x for x in [nz(div.get("day_of_week")), nz(div.get("muscle_groups"))] if x)
        rb.subsection_title(f"{title}" + (f"  —  {extra}" if extra else ""))

        if not exercises:
            rb.paragraph("Nenhum exercício cadastrado nesta divisão.", muted=True, size=9.5, italic=True)
            continue

        rows = []
        for ex in exercises:
            sets_desc = _sets_summary(ex["sets"])
            rows.append([ex["name"], nz(ex.get("equipment")) or "—", sets_desc, nz(ex.get("notes")) or "—"])
        rb.table(
            headers=["Exercício", "Equipamento", "Séries planejadas", "Observações"],
            rows=rows,
            col_widths=[4.2, 3.0, 6.0, 4.0],
            align=["left", "left", "left", "left"],
        )

    # Evolução de carga — só exercícios com pelo menos 2 registros de histórico.
    charts_data = []
    for div, exercises in division_payload:
        for ex in exercises:
            df_hist = get_weight_history(user_id, ex["id"])
            if df_hist is not None and len(df_hist) >= 2:
                charts_data.append((ex["name"], df_hist.sort_values("log_date")))

    if charts_data:
        rb.section_title("Evolução de carga", "📈")
        apply_chart_style()
        for name, df_hist in charts_data[:8]:
            rb.paragraph(name, bold=True, size=10)
            _evolution_chart(rb, df_hist)
        if len(charts_data) > 8:
            rb.paragraph(
                f"Mostrando 8 de {len(charts_data)} exercícios com histórico de carga registrado.",
                muted=True, size=8.8, italic=True,
            )
    else:
        rb.section_title("Evolução de carga", "📈")
        rb.empty_state("Ainda não há histórico de carga suficiente (registre pelo menos 2 treinos por exercício).")

    return rb.to_bytes()


def _sets_summary(sets: list) -> str:
    if not sets:
        return "—"
    parts = []
    for s in sorted(sets, key=lambda x: x.get("set_number") or 0):
        reps = nz(s.get("reps"))
        weight = nz(s.get("weight_kg"))
        piece = f"Série {s.get('set_number')}: "
        if reps is not None:
            piece += f"{int(reps)} reps"
        if weight is not None:
            piece += f" @ {float(weight):.1f}kg"
        parts.append(piece)
    return "  |  ".join(parts)


def _evolution_chart(rb, df_hist):
    import matplotlib.pyplot as plt

    dates = df_hist["log_date"]
    labels = [d.strftime("%d/%m") if hasattr(d, "strftime") else str(d) for d in dates]
    weights = df_hist["max_weight"].astype(float)

    fig, ax = plt.subplots(figsize=(9.0, 2.6))
    ax.plot(range(len(labels)), weights, color=CHART["primary"], marker="o", linewidth=2, zorder=3)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=8.5)
    ax.set_ylabel("Carga máx. (kg)", fontsize=8.5)
    ax.grid(axis="y", linestyle="--", alpha=0.5, zorder=0)
    for i, v in enumerate(weights):
        ax.text(i, v, f" {v:.1f}", va="bottom", fontsize=7.8, color=CHART["text"])
    fig.tight_layout()
    rb.chart_image(fig, width_cm=15.5)
