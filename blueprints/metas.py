"""
blueprints/metas.py
Módulo Metas — SMART, separado de Finanças. Cada meta tem:
  - Os 5 campos SMART + valor alvo/atual/unidade e prazo.
  - Um histórico de check-ins de avanço (goal_progress_log) com gráfico.
  - Um plano de ação: atividades/serviços vinculados (activities.goal_id)
    com início/fim — "como farei, quando inicio, quando termino".
  - Cada atividade do plano que estiver atrasada (prazo vencido e não
    concluída) pode/deve ganhar seu próprio plano de ação 5W2H
    (reaproveitando a tabela action_plan já usada em Atividades).
"""

from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash

from database.queries_metas import (
    get_goals, get_goal, upsert_goal, delete_goal,
    get_goals_summary,
    get_goal_progress_log, add_goal_progress, delete_goal_progress,
    get_goal_activities, upsert_goal_activity, delete_goal_activity,
    get_action_plans_for_activity, upsert_action_plan, delete_action_plan,
    activity_is_late,
)

metas_bp = Blueprint("metas", __name__, url_prefix="/metas")


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


# ─── Listagem ────────────────────────────────────────────────────────────
@metas_bp.route("/")
def index():
    status_filter = request.args.get("status") or None
    goals = get_goals(status=status_filter)
    summary = get_goals_summary()
    return render_template("metas/index.html", goals=goals, summary=summary, status_filter=status_filter)


# ─── Criar / editar meta ─────────────────────────────────────────────────
@metas_bp.route("/nova", methods=["POST"])
def create():
    data = _goal_form_data(request.form)
    upsert_goal(data)
    flash("Meta criada com sucesso.", "success")
    return redirect(url_for("metas.index"))


@metas_bp.route("/<int:goal_id>/editar", methods=["POST"])
def update(goal_id):
    data = _goal_form_data(request.form)
    data["id"] = goal_id
    upsert_goal(data)
    flash("Meta atualizada.", "success")
    return redirect(url_for("metas.detail", goal_id=goal_id))


@metas_bp.route("/<int:goal_id>/excluir", methods=["POST"])
def delete(goal_id):
    delete_goal(goal_id)
    flash("Meta excluída.", "success")
    return redirect(url_for("metas.index"))


def _goal_form_data(form):
    return {
        "title": form.get("title", "").strip(),
        "specific": form.get("specific", "").strip(),
        "measurable": form.get("measurable", "").strip(),
        "achievable": form.get("achievable", "").strip(),
        "relevant": form.get("relevant", "").strip(),
        "time_bound": _parse_date(form.get("time_bound")),
        "target_value": form.get("target_value") or 0,
        "current_value": form.get("current_value") or 0,
        "unit": form.get("unit", "un.").strip() or "un.",
        "status": form.get("status", "Em andamento"),
    }


# ─── Detalhe da meta ──────────────────────────────────────────────────────
@metas_bp.route("/<int:goal_id>")
def detail(goal_id):
    goal = get_goal(goal_id)
    if not goal:
        flash("Meta não encontrada.", "error")
        return redirect(url_for("metas.index"))

    progress_log = get_goal_progress_log(goal_id)
    activities = get_goal_activities(goal_id)

    late_activities = [a for a in activities if a["is_late"]]
    action_plans_by_activity = {a["id"]: get_action_plans_for_activity(a["id"]) for a in activities}

    chart_series = [
        {"x": p["log_date"].isoformat() if hasattr(p["log_date"], "isoformat") else p["log_date"], "y": float(p["value"])}
        for p in progress_log
    ]

    return render_template(
        "metas/detail.html",
        goal=goal,
        progress_log=list(reversed(progress_log)),
        activities=activities,
        late_activities=late_activities,
        action_plans_by_activity=action_plans_by_activity,
        chart_series=chart_series,
    )


# ─── Check-in de avanço ───────────────────────────────────────────────────
@metas_bp.route("/<int:goal_id>/progresso", methods=["POST"])
def add_progress(goal_id):
    value = request.form.get("value")
    note = request.form.get("note", "").strip() or None
    log_date = _parse_date(request.form.get("log_date"))
    add_goal_progress(goal_id, value, note, log_date)
    flash("Avanço registrado.", "success")
    return redirect(url_for("metas.detail", goal_id=goal_id))


@metas_bp.route("/progresso/<int:log_id>/excluir", methods=["POST"])
def delete_progress(log_id):
    goal_id = request.form.get("goal_id")
    delete_goal_progress(log_id)
    flash("Registro removido.", "success")
    return redirect(url_for("metas.detail", goal_id=goal_id))


# ─── Plano de ação (atividades/serviços da meta) ─────────────────────────
@metas_bp.route("/<int:goal_id>/atividade/nova", methods=["POST"])
def create_activity(goal_id):
    data = _activity_form_data(request.form)
    data["goal_id"] = goal_id
    upsert_goal_activity(data)
    flash("Atividade adicionada ao plano de ação.", "success")
    return redirect(url_for("metas.detail", goal_id=goal_id))


@metas_bp.route("/atividade/<int:activity_id>/editar", methods=["POST"])
def update_activity(activity_id):
    goal_id = request.form.get("goal_id")
    data = _activity_form_data(request.form)
    data["id"] = activity_id
    data["goal_id"] = goal_id
    upsert_goal_activity(data)
    flash("Atividade atualizada.", "success")
    return redirect(url_for("metas.detail", goal_id=goal_id))


@metas_bp.route("/atividade/<int:activity_id>/excluir", methods=["POST"])
def delete_activity(activity_id):
    goal_id = request.form.get("goal_id")
    delete_goal_activity(activity_id)
    flash("Atividade removida.", "success")
    return redirect(url_for("metas.detail", goal_id=goal_id))


def _activity_form_data(form):
    return {
        "title": form.get("title", "").strip(),
        "description": form.get("description", "").strip(),
        "start_date": _parse_date(form.get("start_date")),
        "end_date": _parse_date(form.get("end_date")),
        "status": form.get("status", "Não iniciado"),
    }


# ─── Plano de ação 5W2H de uma atividade atrasada ────────────────────────
@metas_bp.route("/atividade/<int:activity_id>/plano-acao/novo", methods=["POST"])
def create_action_plan(activity_id):
    goal_id = request.form.get("goal_id")
    data = _action_plan_form_data(request.form)
    data["activity_id"] = activity_id
    upsert_action_plan(data)
    flash("Plano de ação (5W2H) registrado.", "success")
    return redirect(url_for("metas.detail", goal_id=goal_id))


@metas_bp.route("/plano-acao/<int:plan_id>/excluir", methods=["POST"])
def delete_action_plan_route(plan_id):
    goal_id = request.form.get("goal_id")
    delete_action_plan(plan_id)
    flash("Item do plano de ação removido.", "success")
    return redirect(url_for("metas.detail", goal_id=goal_id))


def _action_plan_form_data(form):
    return {
        "what": form.get("what", "").strip(),
        "why": form.get("why", "").strip(),
        "who": form.get("who", "").strip(),
        "when_date": _parse_date(form.get("when_date")),
        "where_place": form.get("where_place", "").strip(),
        "how": form.get("how", "").strip(),
        "how_much": form.get("how_much") or None,
        "status": form.get("status", "Pendente"),
    }
