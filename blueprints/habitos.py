"""
blueprints/habitos.py
Módulo Hábitos — ciclos de 90 dias, checks diários, streaks.
"""

from datetime import datetime, date, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify

from database.queries_habitos import (
    get_habits, upsert_habit, delete_habit,
    get_cycles, get_active_cycle, start_cycle, finish_cycle,
    get_checks, toggle_check, mark_check,
    get_today_habits, calculate_stats,
)

habitos_bp = Blueprint("habitos", __name__, url_prefix="/habitos")

FREQUENCY_TYPES = ["Diário", "Dias da semana", "X vezes por semana"]
WEEKDAY_LABELS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _habit_form_data(form):
    freq_type = form.get("frequency_type", "Diário")
    if freq_type == "Dias da semana":
        days = request.form.getlist("frequency_weekdays")
        freq_days = ",".join(days) if days else "0,1,2,3,4"
    elif freq_type == "X vezes por semana":
        freq_days = form.get("frequency_times", "3").strip() or "3"
    else:
        freq_days = None
    return {
        "name": form.get("name", "").strip(),
        "description": form.get("description", "").strip() or None,
        "category": form.get("category", "Geral").strip() or "Geral",
        "frequency_type": freq_type,
        "frequency_days": freq_days,
        "color": form.get("color", "#3B82F6"),
        "icon": form.get("icon", "🎯").strip() or "🎯",
    }


def _freq_label(h):
    ft = h.get("frequency_type") or "Diário"
    if ft == "Diário":
        return "Todos os dias"
    if ft == "Dias da semana":
        idxs = [int(x) for x in str(h.get("frequency_days") or "").split(",") if x.strip().isdigit()]
        return ", ".join(WEEKDAY_LABELS[i] for i in idxs if 0 <= i < 7) or "—"
    if ft == "X vezes por semana":
        return f"{h.get('frequency_days') or 3}x por semana"
    return ft


# ─── Listagem ───────────────────────────────────────────────────────────
@habitos_bp.route("/")
def index():
    df = get_habits()
    habits = df.to_dict("records") if df is not None and not df.empty else []

    df_today = get_today_habits()
    today_by_habit = {}
    if df_today is not None and not df_today.empty:
        for _, row in df_today.iterrows():
            today_by_habit[int(row["habit_id"])] = row.to_dict()

    for h in habits:
        h["freq_label"] = _freq_label(h)
        t = today_by_habit.get(h["id"])
        if t:
            cycle = {"start_date": t["start_date"], "end_date": t["end_date"]}
            df_checks = get_checks(int(t["cycle_id"]))
            stats = calculate_stats(cycle, df_checks, h)
            h["cycle_id"] = int(t["cycle_id"])
            h["done_today"] = bool(t["done_today"])
            h["stats"] = stats
        else:
            h["cycle_id"] = None
            h["done_today"] = False
            h["stats"] = None

    return render_template("habitos/index.html", habits=habits, frequency_types=FREQUENCY_TYPES, weekday_labels=WEEKDAY_LABELS)


@habitos_bp.route("/novo", methods=["POST"])
def create():
    data = _habit_form_data(request.form)
    if not data["name"]:
        flash("Nome do hábito é obrigatório.", "error")
    else:
        upsert_habit(data)
        flash("Hábito criado.", "success")
    return redirect(url_for("habitos.index"))


@habitos_bp.route("/<int:habit_id>/editar", methods=["POST"])
def update(habit_id):
    data = _habit_form_data(request.form)
    data["id"] = habit_id
    upsert_habit(data)
    flash("Hábito atualizado.", "success")
    return redirect(url_for("habitos.index"))


@habitos_bp.route("/<int:habit_id>/excluir", methods=["POST"])
def delete(habit_id):
    delete_habit(habit_id)
    flash("Hábito removido.", "success")
    return redirect(url_for("habitos.index"))


@habitos_bp.route("/<int:habit_id>/ciclo/iniciar", methods=["POST"])
def cycle_start(habit_id):
    start_cycle(habit_id, date.today())
    flash("Ciclo de 90 dias iniciado.", "success")
    return redirect(url_for("habitos.detail", habit_id=habit_id))


@habitos_bp.route("/<int:habit_id>/hoje/toggle", methods=["POST"])
def toggle_today(habit_id):
    cycle = get_active_cycle(habit_id)
    if cycle:
        toggle_check(cycle["id"], date.today())
    return redirect(request.referrer or url_for("habitos.index"))


# ─── Detalhe do hábito — ciclo ativo, grade de checks, histórico ─────────
@habitos_bp.route("/<int:habit_id>")
def detail(habit_id):
    df = get_habits()
    habits = df.to_dict("records") if df is not None and not df.empty else []
    habit = next((h for h in habits if h["id"] == habit_id), None)
    if not habit:
        flash("Hábito não encontrado.", "error")
        return redirect(url_for("habitos.index"))
    habit["freq_label"] = _freq_label(habit)

    cycle = get_active_cycle(habit_id)
    stats = None
    days_grid = []
    if cycle:
        df_checks = get_checks(cycle["id"])
        stats = calculate_stats(cycle, df_checks, habit)
        done_dates = set()
        if df_checks is not None and not df_checks.empty:
            for _, row in df_checks.iterrows():
                if row.get("done"):
                    d = row["check_date"]
                    done_dates.add(d.date() if hasattr(d, "date") else d)
        start_d = cycle["start_date"]
        end_d = cycle["end_date"]
        today = date.today()
        d = start_d
        while d <= end_d:
            days_grid.append({
                "date": d,
                "done": d in done_dates,
                "future": d > today,
            })
            d += timedelta(days=1)

    df_cycles = get_cycles(habit_id)
    cycles = df_cycles.to_dict("records") if df_cycles is not None and not df_cycles.empty else []

    return render_template(
        "habitos/detail.html",
        habit=habit, cycle=cycle, stats=stats, days_grid=days_grid, cycles=cycles,
    )


@habitos_bp.route("/<int:habit_id>/check/<check_date>/toggle", methods=["POST"])
def toggle_day(habit_id, check_date):
    cycle = get_active_cycle(habit_id)
    if not cycle:
        return jsonify({"ok": False, "error": "Sem ciclo ativo."}), 400
    d = _parse_date(check_date)
    if not d:
        return jsonify({"ok": False, "error": "Data inválida."}), 400
    toggle_check(cycle["id"], d)
    df_checks = get_checks(cycle["id"])
    done = False
    if df_checks is not None and not df_checks.empty:
        row = df_checks[df_checks["check_date"].apply(lambda x: (x.date() if hasattr(x, "date") else x) == d)]
        if not row.empty:
            done = bool(row.iloc[0]["done"])
    return jsonify({"ok": True, "done": done})
