"""
reports/metas_report.py
Relatório em Word do módulo Metas: resumo geral, cada meta com seus campos
SMART, barra de progresso, plano de ação (atividades vinculadas) e o 5W2H
das atividades atrasadas.
"""

from database.queries_metas import (
    get_goals, get_goals_summary, get_goal_progress_log,
    get_goal_activities, get_action_plans_for_activity,
)
from reports.builder import ReportBuilder, apply_chart_style, fmt_date, CHART

SITUATION_LABEL = {
    "concluida": "Concluída",
    "cancelada": "Cancelada",
    "atrasada": "Atrasada",
    "proximo_prazo": "Prazo próximo",
    "em_dia": "Em dia",
}
SITUATION_TONE = {
    "concluida": "success",
    "cancelada": "warning",
    "atrasada": "danger",
    "proximo_prazo": "warning",
    "em_dia": "primary",
}


def build_metas_report(user_id: int, username: str) -> "io.BytesIO":
    goals = get_goals(user_id)
    summary = get_goals_summary(user_id)

    rb = ReportBuilder(
        report_title="Relatório de Metas",
        report_subtitle="Metas SMART — acompanhamento de avanço e plano de ação",
        username=username,
        icon="🎯",
    )

    rb.kpi_row([
        ("Total de metas", summary["total"], "primary"),
        ("Em andamento", summary["ativas"], "info"),
        ("Concluídas", summary["concluidas"], "success"),
        ("Atrasadas", summary["atrasadas"], "danger"),
        ("Progresso médio", f"{summary['media_progresso']:.0f}%", "warning"),
    ])

    if not goals:
        rb.empty_state("Nenhuma meta cadastrada ainda.")
        return rb.to_bytes()

    active = [g for g in goals if g["status"] == "Em andamento"]
    if active:
        rb.section_title("Panorama das metas em andamento", "📊")
        apply_chart_style()
        _progress_chart(rb, active)

    rb.section_title("Detalhamento por meta", "📋")

    order = {"Em andamento": 0, "Concluída": 1, "Cancelada": 2}
    for goal in sorted(goals, key=lambda g: (order.get(g["status"], 9), g["title"])):
        _goal_block(rb, user_id, goal)

    return rb.to_bytes()


def _progress_chart(rb, active_goals):
    import matplotlib.pyplot as plt

    labels = [g["title"][:28] + ("…" if len(g["title"]) > 28 else "") for g in active_goals]
    values = [g["progress_pct"] for g in active_goals]
    colors = []
    for g in active_goals:
        sit = g["situation"]
        colors.append({
            "atrasada": CHART["danger"], "proximo_prazo": CHART["warning"],
            "em_dia": CHART["primary"], "concluida": CHART["success"],
        }.get(sit, CHART["primary"]))

    height = max(2.2, 0.5 * len(labels) + 0.8)
    fig, ax = plt.subplots(figsize=(9.5, height))
    y_pos = range(len(labels))
    ax.barh(y_pos, values, color=colors, height=0.55, zorder=3)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("% concluído", fontsize=9)
    ax.grid(axis="x", linestyle="--", alpha=0.5, zorder=0)
    for i, v in enumerate(values):
        ax.text(min(v + 2, 96), i, f"{v:.0f}%", va="center", fontsize=8.5, color=CHART["text"])
    fig.tight_layout()
    rb.chart_image(fig)


def _goal_block(rb, user_id, goal):
    tone = SITUATION_TONE.get(goal["situation"], "primary")
    rb.subsection_title(f"{goal['title']}  ·  {SITUATION_LABEL.get(goal['situation'], goal['status'])}")

    smart_rows = [
        ("Específica (S)", goal.get("specific") or "—"),
        ("Mensurável (M)", goal.get("measurable") or "—"),
        ("Alcançável (A)", goal.get("achievable") or "—"),
        ("Relevante (R)", goal.get("relevant") or "—"),
        ("Prazo (T)", fmt_date(goal.get("time_bound"))),
    ]
    rb.table(
        headers=["Critério SMART", "Descrição"],
        rows=smart_rows,
        col_widths=[3.6, 13.6],
        align=["left", "left"],
        zebra=True,
    )

    right = f"{goal.get('current_value', 0):.0f} / {goal.get('target_value', 0):.0f} {goal.get('unit', '')}"
    rb.progress_bar(f"Progresso — {goal['progress_pct']:.0f}%", goal["progress_pct"], right_text=right, tone=tone)

    activities = get_goal_activities(user_id, goal["id"])
    if activities:
        rows = []
        row_tones = {}
        for i, a in enumerate(activities):
            rows.append([
                a["title"],
                fmt_date(a.get("start_date")),
                fmt_date(a.get("end_date")),
                a.get("status") or "—",
            ])
            if a.get("is_late"):
                row_tones[i] = "danger"
        rb.paragraph("Plano de ação (atividades vinculadas):", bold=True, size=9.8)
        rb.table(
            headers=["Atividade", "Início", "Fim", "Status"],
            rows=rows,
            col_widths=[8.2, 3.0, 3.0, 3.0],
            align=["left", "center", "center", "center"],
            row_tones=row_tones,
        )

        late = [a for a in activities if a.get("is_late")]
        for a in late:
            plans = get_action_plans_for_activity(user_id, a["id"])
            if plans:
                rb.paragraph(f"5W2H — {a['title']} (atrasada)", bold=True, size=9.5, muted=False)
                plan_rows = [
                    [p.get("what") or "—", p.get("why") or "—", p.get("who") or "—",
                     fmt_date(p.get("when_date")), p.get("status") or "—"]
                    for p in plans
                ]
                rb.table(
                    headers=["O quê", "Por quê", "Quem", "Quando", "Status"],
                    rows=plan_rows,
                    col_widths=[4.4, 4.4, 3.2, 2.6, 2.6],
                    align=["left", "left", "left", "center", "center"],
                )
    else:
        rb.paragraph("Nenhuma atividade vinculada ao plano de ação desta meta.", muted=True, size=9.5, italic=True)

    log = get_goal_progress_log(user_id, goal["id"])
    if log:
        rb.paragraph(f"Histórico de avanço ({len(log)} check-in(s)):", bold=True, size=9.8)
        recent = list(reversed(log))[:8]
        rows = [[fmt_date(p["log_date"]), f"{float(p['value']):.1f} {goal.get('unit', '')}", p.get("note") or "—"] for p in recent]
        rb.table(
            headers=["Data", "Valor registrado", "Observação"],
            rows=rows,
            col_widths=[3.0, 4.0, 10.2],
            align=["center", "center", "left"],
        )

    rb.spacer(6)
