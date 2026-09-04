"""
blueprints/saude.py
Módulo Saúde — Musculação (divisões, exercícios, séries, log de treino,
evolução de carga) e Nutrição (alimentos, refeições, macros do dia).

A base de alimentos (`foods`) é compartilhada entre todos os usuários (não
é dado pessoal) — as rotas de alimentos não recebem/filtram user_id.
"""

from datetime import datetime, date, time as dtime

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, g, Response

from database.queries_saude import (
    get_divisions, upsert_division, delete_division, update_division_field,
    get_exercises, get_all_exercises, upsert_exercise, delete_exercise, update_exercise_field,
    get_exercise_sets, upsert_exercise_set, delete_exercise_set, update_set_field,
    get_workout_log, get_weight_history, save_workout_log,
    get_foods, upsert_food, delete_food, update_food_field, seed_foods_if_empty,
    get_meals, upsert_meal, delete_meal,
    get_meal_items, add_meal_item, delete_meal_item,
    get_daily_totals, get_macro_goals, save_macro_goals,
)

saude_bp = Blueprint("saude", __name__, url_prefix="/saude")


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _field_update_response(update_fn, *args):
    body = request.get_json(silent=True) or {}
    try:
        update_fn(*args, body.get("field", ""), body.get("value"))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except PermissionError as e:
        return jsonify({"ok": False, "error": str(e)}), 404
    return jsonify({"ok": True})


@saude_bp.route("/")
def index():
    user_id = g.user_id
    today = date.today()
    df_div = get_divisions(user_id)
    divisions_count = len(df_div) if df_div is not None else 0

    totals = get_daily_totals(user_id, today)
    goals = get_macro_goals(user_id)

    return render_template(
        "saude/index.html",
        divisions_count=divisions_count, totals=totals, goals=goals, today=today,
    )


# ══════════════════════════════════════════════════════════════════════════
# MUSCULAÇÃO
# ══════════════════════════════════════════════════════════════════════════

@saude_bp.route("/musculacao")
def musculacao():
    df = get_divisions(g.user_id)
    divisions = df.to_dict("records") if df is not None and not df.empty else []
    return render_template("saude/musculacao.html", divisions=divisions)


@saude_bp.route("/musculacao/relatorio")
def relatorio_treino():
    from reports.saude_treino_report import build_treino_report
    buf = build_treino_report(g.user_id, g.username)
    filename = f"ficha-de-treino-{date.today().isoformat()}.docx"
    return Response(
        buf.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@saude_bp.route("/musculacao/divisao", methods=["POST"])
def create_division():
    upsert_division(g.user_id, {"name": "Nova divisão"})
    return jsonify({"ok": True})


@saude_bp.route("/musculacao/divisao/<int:div_id>/campo", methods=["POST"])
def update_division_field_route(div_id):
    return _field_update_response(update_division_field, g.user_id, div_id)


@saude_bp.route("/musculacao/divisao/<int:div_id>/excluir", methods=["POST"])
def delete_division_route(div_id):
    try:
        delete_division(g.user_id, div_id)
        flash("Divisão removida.", "success")
    except PermissionError:
        flash("Divisão não encontrada.", "error")
    return redirect(url_for("saude.musculacao"))


@saude_bp.route("/musculacao/<int:div_id>")
def division_detail(div_id):
    user_id = g.user_id
    df_div = get_divisions(user_id)
    divisions = df_div.to_dict("records") if df_div is not None and not df_div.empty else []
    division = next((d for d in divisions if d["id"] == div_id), None)
    if not division:
        flash("Divisão não encontrada.", "error")
        return redirect(url_for("saude.musculacao"))

    df_ex = get_exercises(user_id, div_id)
    exercises = df_ex.to_dict("records") if df_ex is not None and not df_ex.empty else []
    for e in exercises:
        df_sets = get_exercise_sets(user_id, e["id"])
        e["sets"] = df_sets.to_dict("records") if df_sets is not None and not df_sets.empty else []

    return render_template("saude/division_detail.html", division=division, exercises=exercises)


@saude_bp.route("/musculacao/<int:div_id>/exercicio", methods=["POST"])
def create_exercise(div_id):
    try:
        upsert_exercise(g.user_id, {"division_id": div_id, "name": "Novo exercício"})
        return jsonify({"ok": True})
    except PermissionError as e:
        return jsonify({"ok": False, "error": str(e)}), 404


@saude_bp.route("/musculacao/exercicio/<int:ex_id>/campo", methods=["POST"])
def update_exercise_field_route(ex_id):
    return _field_update_response(update_exercise_field, g.user_id, ex_id)


@saude_bp.route("/musculacao/exercicio/<int:ex_id>/excluir", methods=["POST"])
def delete_exercise_route(ex_id):
    div_id = request.form.get("div_id")
    try:
        delete_exercise(g.user_id, ex_id)
        flash("Exercício removido.", "success")
    except PermissionError:
        flash("Exercício não encontrado.", "error")
    return redirect(url_for("saude.division_detail", div_id=div_id) if div_id else url_for("saude.musculacao"))


@saude_bp.route("/musculacao/exercicio/<int:ex_id>/serie", methods=["POST"])
def create_set(ex_id):
    user_id = g.user_id
    df_sets = get_exercise_sets(user_id, ex_id)
    next_num = (int(df_sets["set_number"].max()) + 1) if df_sets is not None and not df_sets.empty else 1
    try:
        upsert_exercise_set(user_id, {"exercise_id": ex_id, "set_number": next_num, "reps": 10, "weight_kg": 0})
        return jsonify({"ok": True})
    except PermissionError as e:
        return jsonify({"ok": False, "error": str(e)}), 404


@saude_bp.route("/musculacao/serie/<int:set_id>/campo", methods=["POST"])
def update_set_field_route(set_id):
    return _field_update_response(update_set_field, g.user_id, set_id)


@saude_bp.route("/musculacao/serie/<int:set_id>/excluir", methods=["POST"])
def delete_set_route(set_id):
    ex_id = request.form.get("ex_id")
    div_id = request.form.get("div_id")
    try:
        delete_exercise_set(g.user_id, set_id)
        flash("Série removida.", "success")
    except PermissionError:
        flash("Série não encontrada.", "error")
    return redirect(url_for("saude.division_detail", div_id=div_id) if div_id else url_for("saude.musculacao"))


@saude_bp.route("/musculacao/exercicio/<int:ex_id>")
def exercise_detail(ex_id):
    user_id = g.user_id
    df_all = get_all_exercises(user_id)
    exercises = df_all.to_dict("records") if df_all is not None and not df_all.empty else []
    exercise = next((e for e in exercises if e["id"] == ex_id), None)
    if not exercise:
        flash("Exercício não encontrado.", "error")
        return redirect(url_for("saude.musculacao"))

    df_sets = get_exercise_sets(user_id, ex_id)
    planned_sets = df_sets.to_dict("records") if df_sets is not None and not df_sets.empty else []

    today = date.today()
    df_log_today = get_workout_log(user_id, ex_id, today)
    log_by_set = {}
    if df_log_today is not None and not df_log_today.empty:
        for _, row in df_log_today.iterrows():
            log_by_set[int(row["set_number"])] = row.to_dict()

    df_history = get_weight_history(user_id, ex_id)
    history = []
    if df_history is not None and not df_history.empty:
        for _, row in df_history.sort_values("log_date").iterrows():
            d = row["log_date"]
            history.append({
                "x": (d.isoformat() if hasattr(d, "isoformat") else str(d)),
                "y": float(row["max_weight"]) if row["max_weight"] is not None else 0,
            })

    return render_template(
        "saude/exercise_detail.html",
        exercise=exercise, planned_sets=planned_sets, log_by_set=log_by_set,
        history=history, today=today,
    )


@saude_bp.route("/musculacao/exercicio/<int:ex_id>/log", methods=["POST"])
def save_log(ex_id):
    set_numbers = request.form.getlist("set_number")
    reps_list = request.form.getlist("reps_done")
    weight_list = request.form.getlist("weight_done")
    sets = []
    for sn, reps, weight in zip(set_numbers, reps_list, weight_list):
        try:
            sets.append({
                "set_number": int(sn),
                "reps_done": int(reps) if reps else None,
                "weight_done": float(weight.replace(",", ".")) if weight else None,
            })
        except (TypeError, ValueError):
            continue
    try:
        save_workout_log(g.user_id, ex_id, date.today(), sets)
        flash("Treino de hoje registrado.", "success")
    except PermissionError:
        flash("Exercício não encontrado.", "error")
    return redirect(url_for("saude.exercise_detail", ex_id=ex_id))


# ══════════════════════════════════════════════════════════════════════════
# NUTRIÇÃO — refeições/itens/metas são pessoais (por usuário); a base de
# alimentos é compartilhada (sem user_id, de propósito).
# ══════════════════════════════════════════════════════════════════════════

@saude_bp.route("/nutricao")
def nutricao():
    user_id = g.user_id
    seed_foods_if_empty()
    meal_date = _parse_date(request.args.get("data")) or date.today()

    df_meals = get_meals(user_id, meal_date)
    meals = df_meals.to_dict("records") if df_meals is not None and not df_meals.empty else []
    for m in meals:
        df_items = get_meal_items(user_id, m["id"])
        # Nunca usar a chave "items": em dicts, {{ m.items }} no Jinja resolve
        # para o método builtin dict.items (getattr vence sobre getitem),
        # não para esta chave — por isso "food_items".
        m["food_items"] = df_items.to_dict("records") if df_items is not None and not df_items.empty else []
        m["kcal"] = sum(float(i["item_kcal"] or 0) for i in m["food_items"])

    totals = get_daily_totals(user_id, meal_date)
    goals = get_macro_goals(user_id)

    df_foods = get_foods()
    foods = df_foods.to_dict("records") if df_foods is not None and not df_foods.empty else []

    return render_template(
        "saude/nutricao.html",
        meal_date=meal_date, meals=meals, totals=totals, goals=goals, foods=foods,
    )


@saude_bp.route("/nutricao/relatorio")
def relatorio_nutricao():
    from reports.saude_nutricao_report import build_nutricao_report
    meal_date = _parse_date(request.args.get("data")) or date.today()
    buf = build_nutricao_report(g.user_id, g.username, meal_date=meal_date)
    filename = f"relatorio-nutricao-{meal_date.isoformat()}.docx"
    return Response(
        buf.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@saude_bp.route("/nutricao/refeicao", methods=["POST"])
def create_meal():
    meal_date = _parse_date(request.form.get("meal_date")) or date.today()
    name = request.form.get("name", "").strip() or "Refeição"
    meal_time = request.form.get("meal_time") or None
    upsert_meal(g.user_id, {"name": name, "meal_time": meal_time, "meal_date": meal_date})
    flash("Refeição adicionada.", "success")
    return redirect(url_for("saude.nutricao", data=meal_date.isoformat()))


@saude_bp.route("/nutricao/refeicao/<int:meal_id>/excluir", methods=["POST"])
def delete_meal_route(meal_id):
    meal_date = request.form.get("meal_date") or date.today().isoformat()
    try:
        delete_meal(g.user_id, meal_id)
        flash("Refeição removida.", "success")
    except PermissionError:
        flash("Refeição não encontrada.", "error")
    return redirect(url_for("saude.nutricao", data=meal_date))


@saude_bp.route("/nutricao/refeicao/<int:meal_id>/item", methods=["POST"])
def add_item(meal_id):
    meal_date = request.form.get("meal_date") or date.today().isoformat()
    food_id = request.form.get("food_id")
    quantity_g = request.form.get("quantity_g")
    if not food_id or not quantity_g:
        flash("Escolha o alimento e a quantidade.", "error")
    else:
        try:
            add_meal_item(g.user_id, meal_id, int(food_id), float(quantity_g))
        except (TypeError, ValueError):
            pass
        except PermissionError:
            flash("Refeição não encontrada.", "error")
    return redirect(url_for("saude.nutricao", data=meal_date))


@saude_bp.route("/nutricao/item/<int:item_id>/excluir", methods=["POST"])
def delete_item(item_id):
    meal_date = request.form.get("meal_date") or date.today().isoformat()
    try:
        delete_meal_item(g.user_id, item_id)
    except PermissionError:
        flash("Item não encontrado.", "error")
    return redirect(url_for("saude.nutricao", data=meal_date))


@saude_bp.route("/nutricao/metas", methods=["POST"])
def save_goals():
    try:
        save_macro_goals(
            g.user_id,
            float(request.form.get("protein_g", 0) or 0),
            float(request.form.get("carbs_g", 0) or 0),
            float(request.form.get("fat_g", 0) or 0),
            float(request.form.get("goal_kcal", 0) or 0),
        )
        flash("Metas de macros atualizadas.", "success")
    except (TypeError, ValueError):
        flash("Valores inválidos.", "error")
    return redirect(url_for("saude.nutricao"))


@saude_bp.route("/nutricao/alimentos")
def foods_list():
    seed_foods_if_empty()
    search = request.args.get("q") or None
    df = get_foods(search=search)
    foods = df.to_dict("records") if df is not None and not df.empty else []
    return render_template("saude/alimentos.html", foods=foods, search=search or "")


@saude_bp.route("/nutricao/alimentos/novo", methods=["POST"])
def create_food():
    upsert_food({"name": f"Novo alimento {datetime.now().strftime('%H%M%S')}", "preparation": "Cru"})
    return jsonify({"ok": True})


@saude_bp.route("/nutricao/alimentos/<int:food_id>/campo", methods=["POST"])
def update_food_field_route(food_id):
    return _field_update_response(update_food_field, food_id)


@saude_bp.route("/nutricao/alimentos/<int:food_id>/excluir", methods=["POST"])
def delete_food_route(food_id):
    delete_food(food_id)
    flash("Alimento removido.", "success")
    return redirect(url_for("saude.foods_list"))
