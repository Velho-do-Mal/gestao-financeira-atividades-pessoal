"""
blueprints/atividades.py
Módulo Atividades — tarefas/ações do dia a dia (fora do plano de ação de
uma meta, que fica dentro de Metas). Reaproveita as tabelas `activities`
(parent_id para hierarquia, priority = matriz de Eisenhower) e
`action_plan` (5W2H), já usadas em Metas.
"""

from datetime import datetime, date, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify

from database.queries import (
    get_activities, upsert_activity, delete_activity,
    update_activity_field,
    get_action_plans, upsert_action_plan, delete_action_plan,
    update_action_plan_field,
)

atividades_bp = Blueprint("atividades", __name__, url_prefix="/atividades")

PRIORITIES = [
    "Urgente-Urgente",
    "Importante-Urgente",
    "Importante não Urgente",
    "Não importante-Não urgente",
]
STATUS_LIST = ["Não iniciado", "Em andamento", "Concluído"]


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


# ─── Listagem / tabela editável ────────────────────────────────────────────
@atividades_bp.route("/")
def index():
    today = date.today()

    f_priority = request.args.get("priority") or ""
    f_status = request.args.get("status") or ""
    f_quick = request.args.get("quick") or ""

    df = get_activities(only_standalone=True)
    activities = df.to_dict("records") if df is not None and not df.empty else []

    titles_by_id = {a["id"]: a["title"] for a in activities}
    for a in activities:
        a["parent_title"] = titles_by_id.get(a["parent_id"]) if a.get("parent_id") else None
        a["is_late"] = bool(
            a.get("end_date") and a["status"] != "Concluído"
            and (a["end_date"].date() if hasattr(a["end_date"], "date") else a["end_date"]) < today
        )

    if f_priority:
        activities = [a for a in activities if a["priority"] == f_priority]
    if f_status:
        activities = [a for a in activities if a["status"] == f_status]
    if f_quick == "hoje":
        activities = [a for a in activities if a.get("end_date") and (
            a["end_date"].date() if hasattr(a["end_date"], "date") else a["end_date"]) == today]
    elif f_quick == "semana":
        limit = today + timedelta(days=7)
        activities = [a for a in activities if a.get("end_date") and today <= (
            a["end_date"].date() if hasattr(a["end_date"], "date") else a["end_date"]) <= limit]

    # Agenda — próximos 14 dias, agrupada por data (só quem tem end_date).
    agenda = {}
    for a in activities:
        if a.get("end_date") and a["status"] != "Concluído":
            d = a["end_date"].date() if hasattr(a["end_date"], "date") else a["end_date"]
            if today <= d <= today + timedelta(days=14):
                agenda.setdefault(d, []).append(a)
    agenda_days = [(d, agenda[d]) for d in sorted(agenda.keys())]

    parent_options = [a for a in (df.to_dict("records") if df is not None and not df.empty else []) if not a.get("parent_id")]

    counts = {
        "total": len(df) if df is not None else 0,
        "atrasadas": sum(1 for a in (df.to_dict("records") if df is not None and not df.empty else [])
                          if a.get("end_date") and a["status"] != "Concluído"
                          and (a["end_date"].date() if hasattr(a["end_date"], "date") else a["end_date"]) < today),
        "concluidas": sum(1 for a in (df.to_dict("records") if df is not None and not df.empty else []) if a["status"] == "Concluído"),
    }

    df_plans = get_action_plans(only_standalone=True)
    action_plans = df_plans.to_dict("records") if df_plans is not None and not df_plans.empty else []
    activity_options = df.to_dict("records") if df is not None and not df.empty else []

    return render_template(
        "atividades/index.html",
        activities=activities,
        priorities=PRIORITIES,
        status_list=STATUS_LIST,
        f_priority=f_priority, f_status=f_status, f_quick=f_quick,
        agenda_days=agenda_days,
        parent_options=parent_options,
        counts=counts,
        action_plans=action_plans,
        activity_options=activity_options,
        today=today,
    )


@atividades_bp.route("/rapida", methods=["POST"])
def create_quick():
    activity_id = upsert_activity({
        "title": "Nova atividade",
        "priority": "Importante não Urgente",
        "status": "Não iniciado",
    })
    return jsonify({"ok": True, "id": activity_id})


@atividades_bp.route("/<int:activity_id>/campo", methods=["POST"])
def update_field(activity_id):
    body = request.get_json(silent=True) or {}
    try:
        update_activity_field(activity_id, body.get("field", ""), body.get("value"))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True})


@atividades_bp.route("/<int:activity_id>/excluir", methods=["POST"])
def delete(activity_id):
    delete_activity(activity_id)
    flash("Atividade excluída.", "success")
    return redirect(url_for("atividades.index"))


# ─── Plano de ação 5W2H (fora de metas) ────────────────────────────────────
@atividades_bp.route("/plano-acao/rapido", methods=["POST"])
def create_plan_quick():
    body = request.get_json(silent=True) or {}
    activity_id = body.get("activity_id")
    if not activity_id:
        df = get_activities(only_standalone=True)
        if df is None or df.empty:
            return jsonify({"ok": False, "error": "Crie uma atividade antes de adicionar um item do plano 5W2H."}), 400
        activity_id = int(df.iloc[0]["id"])
    plan_id = upsert_action_plan({
        "activity_id": activity_id,
        "what": "", "why": "", "who": "", "when_date": None,
        "where_place": "", "how": "", "how_much": None, "status": "Pendente",
    })
    return jsonify({"ok": True, "id": plan_id})


@atividades_bp.route("/plano-acao/<int:plan_id>/campo", methods=["POST"])
def update_plan_field(plan_id):
    body = request.get_json(silent=True) or {}
    try:
        update_action_plan_field(plan_id, body.get("field", ""), body.get("value"))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True})


@atividades_bp.route("/plano-acao/<int:plan_id>/excluir", methods=["POST"])
def delete_plan(plan_id):
    delete_action_plan(plan_id)
    flash("Item do plano de ação removido.", "success")
    return redirect(url_for("atividades.index"))
