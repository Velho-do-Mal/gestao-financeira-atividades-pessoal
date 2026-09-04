"""
blueprints/atividades.py
Módulo Atividades — tarefas/ações do dia a dia (fora do plano de ação de
uma meta, que fica dentro de Metas). Reaproveita as tabelas `activities`
(parent_id para hierarquia, priority = matriz de Eisenhower) e
`action_plan` (5W2H), já usadas em Metas.
"""

from datetime import datetime, date, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, g

from database.queries import (
    get_activities, upsert_activity, delete_activity,
    update_activity_field,
    get_action_plans, upsert_action_plan, delete_action_plan,
    update_action_plan_field,
)
from utils.helpers import priority_color, priority_emoji

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


def _as_date(value):
    """Normaliza datetime/date/None vindos do banco para `date` puro."""
    if value is None:
        return None
    return value.date() if hasattr(value, "date") else value


def _status_badge(status, end_date, today):
    """Indicador nº1 — bem visual — do andamento da atividade: Atrasada /
    Vence hoje / No prazo / Concluída. É o que o usuário pediu pra "bater
    o olho e identificar o que está pronto"."""
    if status == "Concluído":
        return {"label": "Concluída", "icon": "✅", "css": "badge-success"}
    d = _as_date(end_date)
    if d and d < today:
        return {"label": "Atrasada", "icon": "🔴", "css": "badge-danger"}
    if d and d == today:
        return {"label": "Vence hoje", "icon": "🟡", "css": "badge-warning"}
    return {"label": "No prazo", "icon": "🔵", "css": "badge-info"}


def _priority_badge(priority):
    """Indicador nº2 — bem visual — da prioridade (matriz de Eisenhower),
    pra identificar o que é urgente/importante batendo o olho."""
    return {"label": priority or "—", "emoji": priority_emoji(priority), "color": priority_color(priority)}


def _build_activity_tree(all_activities, matched_ids, today):
    """Monta a lista de atividades em ordem de árvore (pré-ordem, qualquer
    profundidade) com `depth` calculado — é isso que dá a indentação visual
    correta na tabela. Antes a "hierarquia" dependia de um ORDER BY em SQL
    que só agrupava pai+filho de 1 nível e não se atualizava direito quando
    o usuário trocava o pai de uma atividade pela combobox — daí o bug
    relatado ("seleciono o pai e não identa").

    Também blinda contra ciclos nos dados (proteção extra — a validação
    principal já impede criar um ciclo em database/queries.py) e contra pai
    "órfão" (fora do conjunto, ex.: filtrado por only_standalone), tratando
    esses casos como raiz em vez de sumir com a atividade ou travar.

    `matched_ids`: ids que batem com os filtros ativos (prioridade/status/
    prazo). Uma atividade fora do filtro ainda aparece (com `dim=True`) se
    for ancestral de alguma atividade que bateu — senão a árvore fica
    "furada" (filho visível sem o pai por perto).
    """
    by_id = {a["id"]: a for a in all_activities}
    all_ids = set(by_id.keys())
    for a in all_activities:
        if a.get("parent_id") is not None and a["parent_id"] not in all_ids:
            a["parent_id"] = None  # pai fora do conjunto — trata como raiz

    children_map = {}
    for a in all_activities:
        children_map.setdefault(a.get("parent_id"), []).append(a)
    for kids in children_map.values():
        kids.sort(key=lambda x: (x.get("order_index") or 0, (x.get("title") or "").lower()))

    keep_ids = set(matched_ids)
    for aid in list(matched_ids):
        cur = by_id.get(aid)
        while cur and cur.get("parent_id") is not None:
            keep_ids.add(cur["parent_id"])
            cur = by_id.get(cur["parent_id"])

    ordered = []

    def _visit(node, depth, visited):
        if node["id"] in visited or node["id"] not in keep_ids:
            return
        visited = visited | {node["id"]}
        item = dict(node)
        item["depth"] = depth
        item["dim"] = node["id"] not in matched_ids
        item["is_late"] = bool(
            item.get("end_date") and item["status"] != "Concluído"
            and _as_date(item["end_date"]) < today
        )
        item["status_badge"] = _status_badge(item.get("status"), item.get("end_date"), today)
        item["priority_badge"] = _priority_badge(item.get("priority"))
        ordered.append(item)
        for child in children_map.get(node["id"], []):
            _visit(child, depth + 1, visited)

    for root in children_map.get(None, []):
        _visit(root, 0, set())

    return ordered


def _descendant_ids(all_activities, activity_id):
    """Ids de todas as subatividades (qualquer profundidade) de
    `activity_id` — usado para nunca oferecer, no seletor de "Pai", uma
    opção que criaria um ciclo (a validação de verdade fica no backend em
    database/queries.py; isso aqui só evita mostrar uma opção inválida)."""
    children_map = {}
    for a in all_activities:
        children_map.setdefault(a.get("parent_id"), []).append(a["id"])
    result = set()
    stack = list(children_map.get(activity_id, []))
    while stack:
        cid = stack.pop()
        if cid in result:
            continue
        result.add(cid)
        stack.extend(children_map.get(cid, []))
    return result


# ─── Listagem / tabela editável ────────────────────────────────────────────
@atividades_bp.route("/")
def index():
    user_id = g.user_id
    today = date.today()

    f_priority = request.args.get("priority") or ""
    f_status = request.args.get("status") or ""
    f_quick = request.args.get("quick") or ""

    df = get_activities(user_id, only_standalone=True)
    all_activities = df.to_dict("records") if df is not None and not df.empty else []

    def _end(a):
        return a["end_date"].date() if hasattr(a.get("end_date"), "date") else a.get("end_date")

    def _matches(a):
        if f_priority and a["priority"] != f_priority:
            return False
        if f_status and a["status"] != f_status:
            return False
        if f_quick == "hoje":
            d = _end(a)
            if not (d and d == today):
                return False
        elif f_quick == "semana":
            d = _end(a)
            if not (d and today <= d <= today + timedelta(days=7)):
                return False
        return True

    matched_ids = {a["id"] for a in all_activities if _matches(a)}
    # Monta a árvore em pré-ordem com profundidade — dá a indentação visual
    # correta e mantém pai/filho sempre adjacentes, mesmo depois de trocar
    # o pai pela combobox (ver docstring de _build_activity_tree).
    activities = _build_activity_tree(all_activities, matched_ids, today)

    # Agenda — próximos 14 dias, agrupada por data (baseada em todas as
    # atividades do usuário, não só as visíveis com o filtro atual).
    agenda = {}
    for a in all_activities:
        if a.get("end_date") and a["status"] != "Concluído":
            d = _end(a)
            if today <= d <= today + timedelta(days=14):
                agenda.setdefault(d, []).append(a)
    agenda_days = [(d, agenda[d]) for d in sorted(agenda.keys())]

    # Opções de "Pai" por atividade: qualquer outra atividade, exceto ela
    # mesma e suas próprias subatividades (evita oferecer uma opção que
    # criaria um ciclo — a validação real fica no backend em queries.py).
    for a in activities:
        descendants = _descendant_ids(all_activities, a["id"])
        a["parent_options"] = [
            p for p in all_activities if p["id"] != a["id"] and p["id"] not in descendants
        ]

    counts = {
        "total": len(all_activities),
        "atrasadas": sum(1 for a in all_activities
                          if a.get("end_date") and a["status"] != "Concluído"
                          and _end(a) < today),
        "concluidas": sum(1 for a in all_activities if a["status"] == "Concluído"),
    }

    df_plans = get_action_plans(user_id, only_standalone=True)
    action_plans = df_plans.to_dict("records") if df_plans is not None and not df_plans.empty else []
    activity_options = all_activities

    return render_template(
        "atividades/index.html",
        activities=activities,
        priorities=PRIORITIES,
        status_list=STATUS_LIST,
        f_priority=f_priority, f_status=f_status, f_quick=f_quick,
        agenda_days=agenda_days,
        counts=counts,
        action_plans=action_plans,
        activity_options=activity_options,
        today=today,
    )


@atividades_bp.route("/rapida", methods=["POST"])
def create_quick():
    activity_id = upsert_activity(g.user_id, {
        "title": "Nova atividade",
        "priority": "Importante não Urgente",
        "status": "Não iniciado",
    })
    return jsonify({"ok": True, "id": activity_id})


@atividades_bp.route("/<int:activity_id>/campo", methods=["POST"])
def update_field(activity_id):
    body = request.get_json(silent=True) or {}
    try:
        update_activity_field(g.user_id, activity_id, body.get("field", ""), body.get("value"))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except PermissionError as e:
        return jsonify({"ok": False, "error": str(e)}), 404
    return jsonify({"ok": True})


@atividades_bp.route("/<int:activity_id>/excluir", methods=["POST"])
def delete(activity_id):
    try:
        delete_activity(g.user_id, activity_id)
        flash("Atividade excluída.", "success")
    except PermissionError:
        flash("Atividade não encontrada.", "error")
    return redirect(url_for("atividades.index"))


# ─── Plano de ação 5W2H (fora de metas) ────────────────────────────────────
@atividades_bp.route("/plano-acao/rapido", methods=["POST"])
def create_plan_quick():
    user_id = g.user_id
    body = request.get_json(silent=True) or {}
    activity_id = body.get("activity_id")
    if not activity_id:
        df = get_activities(user_id, only_standalone=True)
        if df is None or df.empty:
            return jsonify({"ok": False, "error": "Crie uma atividade antes de adicionar um item do plano 5W2H."}), 400
        activity_id = int(df.iloc[0]["id"])
    plan_id = upsert_action_plan(user_id, {
        "activity_id": activity_id,
        "what": "", "why": "", "who": "", "when_date": None,
        "where_place": "", "how": "", "how_much": None, "status": "Pendente",
    })
    return jsonify({"ok": True, "id": plan_id})


@atividades_bp.route("/plano-acao/<int:plan_id>/campo", methods=["POST"])
def update_plan_field(plan_id):
    body = request.get_json(silent=True) or {}
    try:
        update_action_plan_field(g.user_id, plan_id, body.get("field", ""), body.get("value"))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except PermissionError as e:
        return jsonify({"ok": False, "error": str(e)}), 404
    return jsonify({"ok": True})


@atividades_bp.route("/plano-acao/<int:plan_id>/excluir", methods=["POST"])
def delete_plan(plan_id):
    try:
        delete_action_plan(g.user_id, plan_id)
        flash("Item do plano de ação removido.", "success")
    except PermissionError:
        flash("Item do plano de ação não encontrado.", "error")
    return redirect(url_for("atividades.index"))
