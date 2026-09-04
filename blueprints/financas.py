"""
blueprints/financas.py
Módulo Finanças — Cadastros (Fornecedores/Categorias/Bancos), Movimentações,
Gerencial e Dashboards. As Metas saíram deste módulo (ver blueprints/metas.py).
"""

from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, g

from database.queries import (
    get_suppliers, upsert_supplier, delete_supplier, update_supplier_field,
    get_categories, get_subcategories, get_all_subcategories,
    upsert_category, upsert_subcategory, delete_category, delete_subcategory,
    update_category_field, update_subcategory_field,
    get_banks, upsert_bank, delete_bank, get_all_bank_balances, update_bank_field,
    get_transactions, insert_transaction, update_transaction, delete_transaction,
    update_transaction_field,
    delete_recurrence_group, get_total_initial_balance, build_cashflow_pivot,
    get_home_summary,
)
from utils.helpers import df_to_excel_bytes

financas_bp = Blueprint("financas", __name__, url_prefix="/financas")


def _parse_float(value, default=0.0):
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def _field_update_response(update_fn, *args):
    """Wrapper comum das rotas de autosave por célula (tabelas editáveis).
    `args` já inclui g.user_id como 1º elemento (passado pelo call site)."""
    body = request.get_json(silent=True) or {}
    try:
        update_fn(*args, body.get("field", ""), body.get("value"))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except PermissionError as e:
        return jsonify({"ok": False, "error": str(e)}), 404
    return jsonify({"ok": True})


@financas_bp.route("/")
def index():
    """Página inicial do módulo Finanças: pendências (a quem, valor, quando
    venceu), com indicador vermelho para o que já está vencido, e o gráfico
    de fluxo de caixa (entradas para cima / saídas para baixo + acumulado)."""
    from datetime import date as _date
    from dateutil.relativedelta import relativedelta
    import pandas as pd

    user_id = g.user_id
    today = _date.today()

    summary = get_home_summary(user_id)

    df_pending = get_transactions(user_id, status="Não pago")
    pending = []
    if df_pending is not None and not df_pending.empty:
        for _, row in df_pending.sort_values("due_date").iterrows():
            due = row["due_date"]
            due_date_obj = due.date() if hasattr(due, "date") else due
            is_overdue = bool(due_date_obj and due_date_obj < today)
            pending.append({
                "id": row["id"],
                "flow_type": row["flow_type"],
                "who": row.get("supplier_name") or row.get("description") or "—",
                "category_name": row.get("category_name") or "—",
                "total_value": float(row["total_value"]),
                "due_date": due,
                "is_overdue": is_overdue,
                "days_overdue": (today - due_date_obj).days if is_overdue else 0,
            })

    # Fluxo de caixa: entradas para cima, saídas para baixo (valor negativo)
    # + linha do acumulado. Período e Previsto/Realizado/Ambos escolhidos
    # pelo usuário; por padrão mostra uma janela de 3 meses antes até 3
    # meses depois de hoje.
    cf_start = _parse_date(request.args.get("cf_de")) or (today.replace(day=1) - relativedelta(months=3))
    cf_end = _parse_date(request.args.get("cf_ate")) or (today.replace(day=1) + relativedelta(months=4) - relativedelta(days=1))
    cf_view = request.args.get("cf_view", "Ambos")
    cf_is_forecast = {"Previsto": True, "Realizado": False, "Ambos": None}.get(cf_view)

    cashflow = {"months": [], "income": [], "expense": [], "accumulated": []}
    df_cf = get_transactions(user_id, start_date=cf_start, end_date=cf_end)
    if df_cf is not None and not df_cf.empty:
        df_cf = df_cf.copy()
        if cf_is_forecast is not None:
            df_cf = df_cf[df_cf["is_forecast"] == cf_is_forecast]
        if not df_cf.empty:
            df_cf["month"] = pd.to_datetime(df_cf["due_date"]).dt.to_period("M").dt.to_timestamp()
            grouped = df_cf.groupby(["month", "flow_type"])["total_value"].sum().reset_index()
            pivot = grouped.pivot(index="month", columns="flow_type", values="total_value").fillna(0).reset_index()
            acc = 0.0
            for _, row in pivot.iterrows():
                inc = float(row.get("Entrada", 0))
                exp = float(row.get("Saída", 0))
                acc += inc - exp
                cashflow["months"].append(row["month"].strftime("%b/%y"))
                cashflow["income"].append(inc)
                cashflow["expense"].append(-exp)
                cashflow["accumulated"].append(acc)

    return render_template(
        "financas/index.html",
        summary=summary,
        pending=pending,
        today=today,
        cashflow=cashflow,
        cf_start=cf_start, cf_end=cf_end, cf_view=cf_view,
    )


# ══════════════════════════════════════════════════════════════════════════
# CADASTROS
# ══════════════════════════════════════════════════════════════════════════

@financas_bp.route("/cadastros")
def cadastros():
    user_id = g.user_id
    sub = request.args.get("sub", "fornecedores")

    suppliers = get_suppliers(user_id)
    suppliers = suppliers.to_dict("records") if suppliers is not None and not suppliers.empty else []

    df_cats = get_categories(user_id)
    categories = df_cats.to_dict("records") if df_cats is not None and not df_cats.empty else []

    subcategories = []
    if df_cats is not None and not df_cats.empty:
        # Uma única query para TODAS as subcategorias (evita N+1 — antes eram
        # N queries, uma por categoria, cada uma com sua própria ida ao banco).
        cat_names = {int(c["id"]): c["name"] for _, c in df_cats.iterrows()}
        df_sub_all = get_all_subcategories(user_id)
        if df_sub_all is not None and not df_sub_all.empty:
            for _, s in df_sub_all.iterrows():
                cid = int(s["category_id"])
                if cid in cat_names:
                    subcategories.append({"id": s["id"], "name": s["name"], "category_id": cid, "category_name": cat_names[cid]})

    df_bal = get_all_bank_balances(user_id)
    banks = df_bal.to_dict("records") if df_bal is not None and not df_bal.empty else []
    total_initial = sum(float(b["initial_balance"]) for b in banks)
    total_current = sum(float(b["current_balance"]) for b in banks)

    return render_template(
        "financas/cadastros.html",
        sub=sub,
        suppliers=suppliers,
        categories=categories,
        subcategories=subcategories,
        banks=banks,
        total_initial=total_initial,
        total_current=total_current,
    )


# ─── Fornecedores ──────────────────────────────────────────────────────────
@financas_bp.route("/fornecedores/salvar", methods=["POST"])
def save_supplier():
    data = {
        "id": request.form.get("id") or None,
        "name": request.form.get("name", "").strip(),
        "document": request.form.get("document", "").strip(),
        "email": request.form.get("email", "").strip(),
        "phone": request.form.get("phone", "").strip(),
        "address": request.form.get("address", "").strip(),
        "notes": request.form.get("notes", "").strip(),
    }
    if not data["name"]:
        flash("Nome do fornecedor é obrigatório.", "error")
    else:
        try:
            upsert_supplier(g.user_id, data)
            flash("Fornecedor salvo.", "success")
        except PermissionError:
            flash("Fornecedor não encontrado.", "error")
    return redirect(url_for("financas.cadastros", sub="fornecedores"))


@financas_bp.route("/fornecedores/<int:supplier_id>/campo", methods=["POST"])
def update_supplier_field_route(supplier_id):
    return _field_update_response(update_supplier_field, g.user_id, supplier_id)


@financas_bp.route("/fornecedores/<int:supplier_id>/excluir", methods=["POST"])
def delete_supplier_route(supplier_id):
    try:
        delete_supplier(g.user_id, supplier_id)
        flash("Fornecedor excluído.", "success")
    except PermissionError:
        flash("Fornecedor não encontrado.", "error")
    return redirect(url_for("financas.cadastros", sub="fornecedores"))


# ─── Categorias / Subcategorias ────────────────────────────────────────────
@financas_bp.route("/categorias/salvar", methods=["POST"])
def save_category():
    cat_id = request.form.get("id") or None
    flow_type = request.form.get("flow_type", "Saída")
    name = request.form.get("name", "").strip()
    if not name:
        flash("Nome da categoria é obrigatório.", "error")
    else:
        try:
            upsert_category(g.user_id, flow_type, name, int(cat_id) if cat_id else None)
            flash("Categoria salva.", "success")
        except PermissionError:
            flash("Categoria não encontrada.", "error")
    return redirect(url_for("financas.cadastros", sub="categorias"))


@financas_bp.route("/categorias/<int:cat_id>/campo", methods=["POST"])
def update_category_field_route(cat_id):
    return _field_update_response(update_category_field, g.user_id, cat_id)


@financas_bp.route("/categorias/<int:cat_id>/excluir", methods=["POST"])
def delete_category_route(cat_id):
    try:
        delete_category(g.user_id, cat_id)
        flash("Categoria excluída.", "success")
    except PermissionError:
        flash("Categoria não encontrada.", "error")
    return redirect(url_for("financas.cadastros", sub="categorias"))


@financas_bp.route("/subcategorias/salvar", methods=["POST"])
def save_subcategory():
    sub_id = request.form.get("id") or None
    category_id = request.form.get("category_id")
    name = request.form.get("name", "").strip()
    if not name or not category_id:
        flash("Categoria e nome da subcategoria são obrigatórios.", "error")
    else:
        try:
            upsert_subcategory(g.user_id, int(category_id), name, int(sub_id) if sub_id else None)
            flash("Subcategoria salva.", "success")
        except PermissionError:
            flash("Categoria ou subcategoria não encontrada.", "error")
    return redirect(url_for("financas.cadastros", sub="categorias"))


@financas_bp.route("/subcategorias/<int:sub_id>/campo", methods=["POST"])
def update_subcategory_field_route(sub_id):
    return _field_update_response(update_subcategory_field, g.user_id, sub_id)


@financas_bp.route("/subcategorias/<int:sub_id>/excluir", methods=["POST"])
def delete_subcategory_route(sub_id):
    try:
        delete_subcategory(g.user_id, sub_id)
        flash("Subcategoria excluída.", "success")
    except PermissionError:
        flash("Subcategoria não encontrada.", "error")
    return redirect(url_for("financas.cadastros", sub="categorias"))


# ─── Bancos ─────────────────────────────────────────────────────────────────
@financas_bp.route("/bancos/salvar", methods=["POST"])
def save_bank():
    data = {
        "id": request.form.get("id") or None,
        "name": request.form.get("name", "").strip(),
        "account": request.form.get("account", "").strip(),
        "agency": request.form.get("agency", "").strip(),
        "initial_balance": _parse_float(request.form.get("initial_balance"), 0.0),
    }
    if not data["name"]:
        flash("Nome do banco é obrigatório.", "error")
    else:
        try:
            upsert_bank(g.user_id, data)
            flash("Banco salvo.", "success")
        except PermissionError:
            flash("Banco não encontrado.", "error")
    return redirect(url_for("financas.cadastros", sub="bancos"))


@financas_bp.route("/bancos/<int:bank_id>/campo", methods=["POST"])
def update_bank_field_route(bank_id):
    return _field_update_response(update_bank_field, g.user_id, bank_id)


@financas_bp.route("/bancos/<int:bank_id>/excluir", methods=["POST"])
def delete_bank_route(bank_id):
    try:
        delete_bank(g.user_id, bank_id)
        flash("Banco excluído.", "success")
    except PermissionError:
        flash("Banco não encontrado.", "error")
    return redirect(url_for("financas.cadastros", sub="bancos"))


# ══════════════════════════════════════════════════════════════════════════
# MOVIMENTAÇÕES
# ══════════════════════════════════════════════════════════════════════════

def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@financas_bp.route("/movimentacoes")
def movimentacoes():
    user_id = g.user_id
    sub = request.args.get("sub", "nova")
    ctx = {"sub": sub}

    if sub == "nova":
        df_cats = get_categories(user_id)
        df_banks = get_banks(user_id)
        df_suppliers = get_suppliers(user_id)
        ctx["categories"] = df_cats.to_dict("records") if df_cats is not None and not df_cats.empty else []
        ctx["banks"] = df_banks.to_dict("records") if df_banks is not None and not df_banks.empty else []
        ctx["suppliers"] = df_suppliers.to_dict("records") if df_suppliers is not None and not df_suppliers.empty else []
        all_subs = get_all_subcategories(user_id)
        ctx["subcategories"] = all_subs.to_dict("records") if all_subs is not None and not all_subs.empty else []

    elif sub == "lancamentos":
        from datetime import date as _date
        start_d = _parse_date(request.args.get("de")) or _date.today().replace(day=1)
        end_d = _parse_date(request.args.get("ate")) or _date.today()
        status = request.args.get("status") or None
        df = get_transactions(user_id, start_date=start_d, end_date=end_d, status=status)
        ctx["transactions"] = df.to_dict("records") if df is not None and not df.empty else []
        ctx["start_d"] = start_d
        ctx["end_d"] = end_d
        ctx["status"] = status or "Todos"
        df_cats = get_categories(user_id)
        df_banks = get_banks(user_id)
        all_subs = get_all_subcategories(user_id)
        ctx["categories"] = df_cats.to_dict("records") if df_cats is not None and not df_cats.empty else []
        ctx["banks"] = df_banks.to_dict("records") if df_banks is not None and not df_banks.empty else []
        ctx["subcategories"] = all_subs.to_dict("records") if all_subs is not None and not all_subs.empty else []

    elif sub == "recorrencias":
        df = get_transactions(user_id)
        groups = []
        if df is not None and not df.empty and "is_recurrent" in df.columns:
            recurrent = df[df["is_recurrent"] == True].copy()
            recurrent = recurrent.dropna(subset=["recurrence_group_id"])
            for gid, grp in recurrent.groupby("recurrence_group_id"):
                first = grp.iloc[0]
                groups.append({
                    "group_id": str(gid),
                    "flow_type": first["flow_type"],
                    "category_name": first.get("category_name") or "—",
                    "description": first.get("description") or "—",
                    "recurrence_type": first.get("recurrence_type") or "Mensal",
                    "parcelas": len(grp),
                    "valor_parcela": float(first["value"]),
                    "valor_total": float(grp["value"].sum()),
                })
        ctx["groups"] = groups
        ctx["total_groups"] = len(groups)
        ctx["total_entradas"] = len([g for g in groups if g["flow_type"] == "Entrada"])
        ctx["total_saidas"] = len([g for g in groups if g["flow_type"] == "Saída"])

    elif sub in ("previsto", "realizado", "diferenca"):
        months = int(request.args.get("meses", 12))
        if sub == "previsto":
            df_table, month_labels = build_cashflow_pivot(user_id, is_forecast=True, months=months)
        elif sub == "realizado":
            df_table, month_labels = build_cashflow_pivot(user_id, is_forecast=False, months=months)
        else:
            df_prev, month_labels = build_cashflow_pivot(user_id, is_forecast=True, months=months)
            df_real, _ = build_cashflow_pivot(user_id, is_forecast=False, months=months)
            if not df_prev.empty:
                df_table = df_prev[["flow_type", "category", "subcategory"]].copy()
                for m in month_labels:
                    p = df_prev[m] if m in df_prev.columns else 0
                    r = df_real[m] if m in df_real.columns else 0
                    df_table[m] = p - r
            else:
                df_table = df_prev

        rows = df_table.to_dict("records") if df_table is not None and not df_table.empty else []
        initial = get_total_initial_balance(user_id)
        totals = {ml: {"in": 0.0, "out": 0.0} for ml in month_labels}
        for r in rows:
            for ml in month_labels:
                v = float(r.get(ml, 0) or 0)
                if r["flow_type"] == "Entrada":
                    totals[ml]["in"] += v
                elif r["flow_type"] == "Saída":
                    totals[ml]["out"] += v
        acc = initial
        footer = []
        for ml in month_labels:
            bal = totals[ml]["in"] - totals[ml]["out"]
            acc += bal
            footer.append({"month": ml, "in": totals[ml]["in"], "out": totals[ml]["out"], "balance": bal, "accumulated": acc})

        ctx["rows"] = rows
        ctx["month_labels"] = month_labels
        ctx["footer"] = footer
        ctx["months"] = months

    return render_template("financas/movimentacoes.html", **ctx)


@financas_bp.route("/movimentacoes/nova", methods=["POST"])
def create_transaction():
    form = request.form
    value = _parse_float(form.get("value"))
    if value <= 0:
        flash("Valor deve ser maior que zero.", "error")
        return redirect(url_for("financas.movimentacoes", sub="nova"))

    status = form.get("status", "Não pago")
    data = {
        "flow_type": form.get("flow_type", "Saída"),
        "category_id": form.get("category_id") or None,
        "subcategory_id": form.get("subcategory_id") or None,
        "supplier_id": form.get("supplier_id") or None,
        "bank_id": form.get("bank_id") or None,
        "description": form.get("description", "").strip(),
        "value": value,
        "interest": _parse_float(form.get("interest"), 0.0),
        "due_date": _parse_date(form.get("due_date")),
        "status": status,
        "payment_date": _parse_date(form.get("payment_date")) if status == "Pago" else None,
        "is_recurrent": form.get("is_recurrent") == "Sim",
        "recurrence_type": form.get("recurrence_type", "Mensal"),
        "notes": form.get("notes", "").strip(),
        "is_forecast": status != "Pago",
    }
    rec_months = int(form.get("recurrence_months") or 0) if data["is_recurrent"] else 0
    insert_transaction(g.user_id, data, recurrence_months=rec_months)
    flash("Movimentação salva.", "success")
    return redirect(url_for("financas.movimentacoes", sub="nova"))


@financas_bp.route("/movimentacoes/<int:tx_id>/editar", methods=["POST"])
def update_transaction_route(tx_id):
    form = request.form
    status = form.get("status", "Não pago")
    data = {
        "flow_type": form.get("flow_type", "Saída"),
        "category_id": form.get("category_id") or None,
        "subcategory_id": form.get("subcategory_id") or None,
        "bank_id": form.get("bank_id") or None,
        "description": form.get("description", "").strip(),
        "value": _parse_float(form.get("value")),
        "interest": _parse_float(form.get("interest"), 0.0),
        "due_date": _parse_date(form.get("due_date")),
        "status": status,
        "payment_date": _parse_date(form.get("payment_date")) if status == "Pago" else None,
    }
    try:
        update_transaction(g.user_id, tx_id, data)
        flash("Movimentação atualizada.", "success")
    except PermissionError:
        flash("Movimentação não encontrada.", "error")
    return redirect(url_for("financas.movimentacoes", sub="lancamentos"))


@financas_bp.route("/movimentacoes/<int:tx_id>/campo", methods=["POST"])
def update_transaction_field_route(tx_id):
    return _field_update_response(update_transaction_field, g.user_id, tx_id)


@financas_bp.route("/movimentacoes/<int:tx_id>/excluir", methods=["POST"])
def delete_transaction_route(tx_id):
    try:
        delete_transaction(g.user_id, tx_id)
        flash("Movimentação excluída.", "success")
    except PermissionError:
        flash("Movimentação não encontrada.", "error")
    return redirect(url_for("financas.movimentacoes", sub="lancamentos"))


@financas_bp.route("/recorrencias/<path:group_id>/excluir", methods=["POST"])
def delete_recurrence_route(group_id):
    delete_recurrence_group(g.user_id, group_id)
    flash("Grupo de recorrência excluído (todas as parcelas).", "success")
    return redirect(url_for("financas.movimentacoes", sub="recorrencias"))


# ══════════════════════════════════════════════════════════════════════════
# GERENCIAL
# ══════════════════════════════════════════════════════════════════════════

@financas_bp.route("/gerencial")
def gerencial():
    from datetime import date as _date
    user_id = g.user_id
    start_d = _parse_date(request.args.get("de")) or _date.today().replace(day=1)
    end_d = _parse_date(request.args.get("ate")) or _date.today()
    view_mode = request.args.get("view", "Ambos")
    is_forecast = {"Previsto": True, "Realizado": False, "Ambos": None}.get(view_mode)

    df_period = get_transactions(user_id, start_date=start_d, end_date=end_d)

    cashflow = {"months": [], "income": [], "expense": [], "accumulated": []}
    total_in = total_out = 0.0
    extrato = []
    df_prev = df_real = None

    if df_period is not None and not df_period.empty:
        import pandas as pd
        df_period = df_period.copy()

        # Pie charts (Previsto x Realizado) sempre refletem o período inteiro,
        # independente do filtro "view" — só o gráfico de fluxo de caixa e o
        # extrato respeitam o view_mode escolhido.
        df_prev = df_period[df_period["is_forecast"] == True]
        df_real = df_period[df_period["is_forecast"] == False]

        df_all = df_period
        if is_forecast is not None:
            df_all = df_all[df_all["is_forecast"] == is_forecast]

    else:
        df_all = df_period

    if df_all is not None and not df_all.empty:
        df_all = df_all.copy()
        df_all["month"] = pd.to_datetime(df_all["due_date"]).dt.to_period("M").dt.to_timestamp()
        grouped = df_all.groupby(["month", "flow_type"])["total_value"].sum().reset_index()
        pivot = grouped.pivot(index="month", columns="flow_type", values="total_value").fillna(0).reset_index()
        acc = 0.0
        for _, row in pivot.iterrows():
            inc = float(row.get("Entrada", 0))
            exp = float(row.get("Saída", 0))
            acc += inc - exp
            cashflow["months"].append(row["month"].strftime("%b/%y"))
            cashflow["income"].append(inc)
            cashflow["expense"].append(exp)
            cashflow["accumulated"].append(acc)

        total_in = float(df_all[df_all["flow_type"] == "Entrada"]["total_value"].sum())
        total_out = float(df_all[df_all["flow_type"] == "Saída"]["total_value"].sum())

        for _, row in df_all.sort_values("due_date").iterrows():
            extrato.append({
                "due_date": row["due_date"], "flow_type": row["flow_type"],
                "category_name": row.get("category_name") or "—",
                "subcategory_name": row.get("subcategory_name") or "—",
                "description": row.get("description") or "",
                "total_value": float(row["total_value"]), "status": row["status"],
                "bank_name": row.get("bank_name") or "—",
            })

    def _pie_data(df):
        if df is None or df.empty:
            return {"labels": [], "values": []}
        out = df[df["flow_type"] == "Saída"]
        if out.empty:
            return {"labels": [], "values": []}
        agg = out.groupby("category_name")["total_value"].sum()
        return {"labels": list(agg.index), "values": [float(v) for v in agg.values]}

    pie_previsto = _pie_data(df_prev)
    pie_realizado = _pie_data(df_real)

    resultado = total_in - total_out

    return render_template(
        "financas/gerencial.html",
        start_d=start_d, end_d=end_d, view_mode=view_mode,
        cashflow=cashflow, total_in=total_in, total_out=total_out, resultado=resultado,
        pie_previsto=pie_previsto, pie_realizado=pie_realizado, extrato=extrato,
    )


@financas_bp.route("/relatorio")
def relatorio():
    from flask import Response
    from datetime import date as _d
    from reports.financas_report import build_financas_report
    buf = build_financas_report(g.user_id, g.username, months=6)
    filename = f"relatorio-financeiro-{_d.today().isoformat()}.docx"
    return Response(
        buf.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@financas_bp.route("/gerencial/exportar")
def export_extrato():
    from datetime import date as _date
    from flask import Response

    start_d = _parse_date(request.args.get("de")) or _date.today().replace(day=1)
    end_d = _parse_date(request.args.get("ate")) or _date.today()
    df = get_transactions(g.user_id, start_date=start_d, end_date=end_d)
    if df is None or df.empty:
        flash("Nenhum lançamento no período para exportar.", "error")
        return redirect(url_for("financas.gerencial", de=start_d.isoformat(), ate=end_d.isoformat()))

    cols = ["due_date", "flow_type", "category_name", "subcategory_name", "description", "total_value", "status", "bank_name"]
    df_show = df[[c for c in cols if c in df.columns]].rename(columns={
        "due_date": "Vencimento", "flow_type": "Tipo", "category_name": "Categoria",
        "subcategory_name": "Subcategoria", "description": "Descrição",
        "total_value": "Valor Total", "status": "Status", "bank_name": "Banco",
    })
    excel_bytes = df_to_excel_bytes(df_show)
    filename = f"extrato_{start_d}_{end_d}.xlsx"
    return Response(
        excel_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ══════════════════════════════════════════════════════════════════════════
# DASHBOARDS
# ══════════════════════════════════════════════════════════════════════════

@financas_bp.route("/dashboards")
def dashboards():
    from datetime import date as _date
    import pandas as pd

    today = _date.today()
    start_d = _parse_date(request.args.get("de")) or today.replace(month=1, day=1)
    end_d = _parse_date(request.args.get("ate")) or today

    df = get_transactions(g.user_id, start_date=start_d, end_date=end_d)
    if df is None or df.empty:
        return render_template("financas/dashboards.html", has_data=False, start_d=start_d, end_d=end_d)

    total_in = float(df[df["flow_type"] == "Entrada"]["total_value"].sum())
    total_out = float(df[df["flow_type"] == "Saída"]["total_value"].sum())
    resultado = total_in - total_out
    inadimplencia = float(df[
        (df["flow_type"] == "Saída") & (df["status"] == "Não pago") &
        (pd.to_datetime(df["due_date"]).dt.date < today)
    ]["total_value"].sum())

    df = df.copy()
    df["month"] = pd.to_datetime(df["due_date"]).dt.to_period("M").dt.to_timestamp()
    grouped = df.groupby(["month", "flow_type"])["total_value"].sum().reset_index()
    pivot = grouped.pivot(index="month", columns="flow_type", values="total_value").fillna(0).reset_index()
    cashflow = {"months": [], "income": [], "expense": [], "accumulated": []}
    acc = 0.0
    for _, row in pivot.iterrows():
        inc = float(row.get("Entrada", 0))
        exp = float(row.get("Saída", 0))
        acc += inc - exp
        cashflow["months"].append(row["month"].strftime("%b/%y"))
        cashflow["income"].append(inc)
        cashflow["expense"].append(exp)
        cashflow["accumulated"].append(acc)

    def _pie(flow_type):
        sub = df[df["flow_type"] == flow_type]
        if sub.empty:
            return {"labels": [], "values": []}
        agg = sub.groupby("category_name")["total_value"].sum()
        return {"labels": list(agg.index), "values": [float(v) for v in agg.values]}

    tips = []
    if inadimplencia > 0:
        tips.append(f"⚠️ Inadimplência detectada: {inadimplencia:.2f} em contas vencidas.")
    if resultado < 0:
        tips.append(f"🔴 Resultado negativo: despesas superaram receitas.")
    if total_out > 0 and (total_out / max(total_in, 1)) > 0.8:
        tips.append("🟡 Comprometimento alto: mais de 80% das receitas comprometidas.")
    if not tips:
        tips.append("✅ Parabéns! Resultado positivo no período.")
    tips += [
        "📌 Revise o orçamento mensalmente e compare com o realizado.",
        "💡 Metas SMART ajudam a manter o foco financeiro.",
        "🏦 Mantenha ao menos 3 meses de despesas como reserva de emergência.",
    ]

    return render_template(
        "financas/dashboards.html", has_data=True, start_d=start_d, end_d=end_d,
        total_in=total_in, total_out=total_out, resultado=resultado, inadimplencia=inadimplencia,
        cashflow=cashflow, pie_saidas=_pie("Saída"), pie_entradas=_pie("Entrada"), tips=tips,
    )
