"""
reports/habitos_report.py
Relatório em Word do módulo Hábitos: panorama geral, % de cumprimento por
hábito no ciclo de 90 dias ativo, streaks e histórico de ciclos anteriores.
"""

from database.queries_habitos import get_habits, get_active_cycle, get_checks, calculate_stats, get_cycles
from reports.builder import ReportBuilder, apply_chart_style, fmt_date, CHART, nz

WEEKDAY_LABELS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def _freq_label(h):
    ft = nz(h.get("frequency_type")) or "Diário"
    if ft == "Diário":
        return "Todos os dias"
    if ft == "Dias da semana":
        idxs = [int(x) for x in str(nz(h.get("frequency_days")) or "").split(",") if x.strip().isdigit()]
        return ", ".join(WEEKDAY_LABELS[i] for i in idxs if 0 <= i < 7) or "—"
    if ft == "X vezes por semana":
        return f"{nz(h.get('frequency_days')) or 3}x por semana"
    return ft


def build_habitos_report(user_id: int, username: str) -> "io.BytesIO":
    df = get_habits(user_id)
    habits = df.to_dict("records") if df is not None and not df.empty else []

    rb = ReportBuilder(
        report_title="Relatório de Hábitos",
        report_subtitle="Ciclos de 90 dias — cumprimento, streaks e consistência",
        username=username,
        icon="🔄",
    )

    if not habits:
        rb.empty_state("Nenhum hábito cadastrado ainda.")
        return rb.to_bytes()

    enriched = []
    for h in habits:
        h["freq_label"] = _freq_label(h)
        cycle = get_active_cycle(user_id, h["id"])
        if cycle:
            df_checks = get_checks(user_id, cycle["id"])
            stats = calculate_stats(cycle, df_checks, h)
            h["cycle"] = cycle
            h["stats"] = stats
        else:
            h["cycle"] = None
            h["stats"] = None
        enriched.append(h)

    with_cycle = [h for h in enriched if h["stats"]]
    total_habits = len(enriched)
    active_cycles = len(with_cycle)
    avg_pct = round(sum(h["stats"]["pct_done"] for h in with_cycle) / len(with_cycle), 1) if with_cycle else 0.0
    avg_streak = round(sum(h["stats"]["current_streak"] for h in with_cycle) / len(with_cycle), 1) if with_cycle else 0.0

    rb.kpi_row([
        ("Hábitos cadastrados", total_habits, "primary"),
        ("Ciclos ativos", active_cycles, "info"),
        ("Cumprimento médio", f"{avg_pct:.0f}%", "success" if avg_pct >= 70 else "warning"),
        ("Streak médio atual", f"{avg_streak:.0f} dias", "warning"),
    ])

    if with_cycle:
        rb.section_title("Cumprimento por hábito (ciclo atual)", "📊")
        apply_chart_style()
        _completion_chart(rb, with_cycle)

    rb.section_title("Detalhamento", "📋")
    rows = []
    row_tones = {}
    for i, h in enumerate(enriched):
        if h["stats"]:
            s = h["stats"]
            rows.append([
                f"{h.get('icon', '🎯')} {h['name']}",
                nz(h.get("category")) or "Geral",
                h["freq_label"],
                f"{s['days_elapsed']}/90",
                f"{s['pct_done']:.0f}%",
                f"{s['current_streak']} dias",
                f"{s['best_streak']} dias",
            ])
            if s["pct_done"] < 50:
                row_tones[i] = "danger"
            elif s["pct_done"] < 75:
                row_tones[i] = "warning"
        else:
            rows.append([f"{h.get('icon', '🎯')} {h['name']}", nz(h.get("category")) or "Geral", h["freq_label"], "—", "Sem ciclo ativo", "—", "—"])

    rb.table(
        headers=["Hábito", "Categoria", "Frequência", "Ciclo (dias)", "Cumprimento", "Streak atual", "Melhor streak"],
        rows=rows,
        col_widths=[4.0, 2.6, 3.0, 2.0, 2.3, 2.1, 2.2],
        align=["left", "left", "left", "center", "center", "center", "center"],
        row_tones=row_tones,
    )

    # Histórico de ciclos concluídos/abandonados (resumo)
    history_rows = []
    for h in enriched:
        df_cycles = get_cycles(user_id, h["id"])
        if df_cycles is None or df_cycles.empty:
            continue
        past = df_cycles[df_cycles["status"] != "Em andamento"]
        for _, c in past.iterrows():
            history_rows.append([
                f"{h.get('icon', '🎯')} {h['name']}",
                fmt_date(c["start_date"]), fmt_date(c["end_date"]), c["status"],
            ])

    if history_rows:
        rb.section_title("Histórico de ciclos anteriores", "🗂️")
        rb.table(
            headers=["Hábito", "Início", "Fim", "Status"],
            rows=history_rows[:20],
            col_widths=[6.0, 3.5, 3.5, 3.0],
            align=["left", "center", "center", "center"],
        )

    return rb.to_bytes()


def _completion_chart(rb, with_cycle):
    import matplotlib.pyplot as plt

    labels = [h["name"][:26] for h in with_cycle]
    values = [h["stats"]["pct_done"] for h in with_cycle]
    colors = [CHART["success"] if v >= 75 else (CHART["warning"] if v >= 50 else CHART["danger"]) for v in values]

    fig, ax = plt.subplots(figsize=(9.5, max(2.2, 0.5 * len(labels) + 0.8)))
    y_pos = range(len(labels))
    ax.barh(y_pos, values, color=colors, height=0.55, zorder=3)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    x_max = max(100, max(values) if values else 100) * 1.12
    ax.set_xlim(0, x_max)
    ax.grid(axis="x", linestyle="--", alpha=0.5, zorder=0)
    for i, v in enumerate(values):
        ax.text(v + x_max * 0.015, i, f"{v:.0f}%", va="center", fontsize=8.5, color=CHART["text"])
    fig.tight_layout()
    rb.chart_image(fig)
