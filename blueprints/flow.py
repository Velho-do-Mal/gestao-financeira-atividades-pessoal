"""
blueprints/flow.py
Módulo Flow — diário do dia, sessões de trabalho profundo (temporizador)
e registros diário/semanal/mensal.
"""

from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, g

from database.queries_flow import (
    get_diary_entry, save_diary_entry, get_diary_entries,
    save_flow_session,
    get_sessions_daily, get_sessions_weekly, get_sessions_monthly,
    get_flow_summary,
)

flow_bp = Blueprint("flow", __name__, url_prefix="/flow")

WEEKDAY_LABELS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@flow_bp.route("/")
def index():
    user_id = g.user_id
    today = date.today()
    diary_today = get_diary_entry(user_id, today)

    summary = get_flow_summary(user_id)

    df_today_sessions = get_sessions_daily(user_id, today)
    sessions_today = df_today_sessions.to_dict("records") if df_today_sessions is not None and not df_today_sessions.empty else []

    df_week = get_sessions_weekly(user_id, today)
    week_start = today - timedelta(days=today.weekday())
    week_by_date = {}
    if df_week is not None and not df_week.empty:
        for _, row in df_week.iterrows():
            d = row["session_date"]
            d = d.date() if hasattr(d, "date") else d
            week_by_date[d] = float(row["total_minutes"] or 0)
    week_chart = {
        "labels": [(week_start + timedelta(days=i)).strftime("%d/%m") for i in range(7)],
        "minutes": [week_by_date.get(week_start + timedelta(days=i), 0) for i in range(7)],
    }

    df_diary = get_diary_entries(user_id, limit=10)
    diary_entries = df_diary.to_dict("records") if df_diary is not None and not df_diary.empty else []

    return render_template(
        "flow/index.html",
        today=today, diary_today=diary_today, summary=summary,
        sessions_today=sessions_today, week_chart=week_chart,
        diary_entries=diary_entries, weekday_labels=WEEKDAY_LABELS,
    )


@flow_bp.route("/diario", methods=["POST"])
def save_diary():
    entry_date = _parse_date(request.form.get("entry_date")) or date.today()
    score = request.form.get("day_score")
    save_diary_entry(g.user_id, {
        "entry_date": entry_date,
        "went_well": request.form.get("went_well", "").strip() or None,
        "could_improve": request.form.get("could_improve", "").strip() or None,
        "gratitude": request.form.get("gratitude", "").strip() or None,
        "day_score": int(score) if score else None,
        "notes": request.form.get("notes", "").strip() or None,
    })
    flash("Diário salvo.", "success")
    return redirect(url_for("flow.index"))


@flow_bp.route("/sessao", methods=["POST"])
def save_session():
    body = request.get_json(silent=True) or {}
    try:
        duration = max(0, int(body.get("duration_minutes", 0)))
    except (TypeError, ValueError):
        duration = 0
    if duration <= 0:
        return jsonify({"ok": False, "error": "Sessão muito curta para registrar."}), 400
    score = body.get("session_score")
    try:
        score = int(score) if score not in (None, "") else None
    except (TypeError, ValueError):
        score = None
    save_flow_session(g.user_id, {
        "session_date": date.today(),
        "started_at": body.get("started_at"),
        "ended_at": datetime.now(),
        "duration_minutes": duration,
        "pause_count": int(body.get("pause_count", 0) or 0),
        "pause_minutes": int(body.get("pause_minutes", 0) or 0),
        "session_score": score,
        "notes": (body.get("notes") or "").strip() or None,
    })
    return jsonify({"ok": True})


@flow_bp.route("/registros")
def records():
    user_id = g.user_id
    period = request.args.get("period", "semanal")
    ref = _parse_date(request.args.get("ref")) or date.today()

    if period == "diario":
        df = get_sessions_daily(user_id, ref)
        rows = df.to_dict("records") if df is not None and not df.empty else []
    elif period == "mensal":
        df = get_sessions_monthly(user_id, ref)
        rows = df.to_dict("records") if df is not None and not df.empty else []
    else:
        period = "semanal"
        df = get_sessions_weekly(user_id, ref)
        rows = df.to_dict("records") if df is not None and not df.empty else []

    return render_template("flow/registros.html", period=period, ref=ref, rows=rows)
