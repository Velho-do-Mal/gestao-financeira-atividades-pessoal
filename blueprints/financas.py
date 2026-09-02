"""
blueprints/financas.py
Módulo Finanças — Cadastros (Fornecedores/Categorias/Bancos), Movimentações,
Gerencial e Dashboards. As Metas saíram deste módulo (ver blueprints/metas.py).
"""

from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash

from database.queries import (
    get_suppliers, upsert_supplier, delete_supplier,
    get_categories, get_subcategories, get_all_subcategories,
    upsert_category, upsert_subcategory, delete_category, delete_subcategory,
    get_banks, upsert_bank, delete_bank, get_all_bank_balances,
)

financas_bp = Blueprint("financas", __name__, url_prefix="/financas")


def _parse_float(value, default=0.0):
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


@financas_bp.route("/")
def index():
    return redirect(url_for("financas.cadastros"))


# ══════════════════════════════════════════════════════════════════════════
# CADASTROS
# ══════════════════════════════════════════════════════════════════════════

@financas_bp.route("/cadastros")
def cadastros():
    sub = request.args.get("sub", "fornecedores")

    suppliers = get_suppliers()
    suppliers = suppliers.to_dict("records") if suppliers is not None and not suppliers.empty else []

    df_cats = get_categories()
    categories = df_cats.to_dict("records") if df_cats is not None and not df_cats.empty else []

    subcategories = []
    if df_cats is not None and not df_cats.empty:
        for _, cat in df_cats.iterrows():
            df_sub = get_subcategories(int(cat["id"]))
            if df_sub is not None and not df_sub.empty:
                for _, s in df_sub.iterrows():
                    subcategories.append({"id": s["id"], "name": s["name"], "category_id": cat["id"], "category_name": cat["name"]})

    df_bal = get_all_bank_balances()
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
        upsert_supplier(data)
        flash("Fornecedor salvo.", "success")
    return redirect(url_for("financas.cadastros", sub="fornecedores"))


@financas_bp.route("/fornecedores/<int:supplier_id>/excluir", methods=["POST"])
def delete_supplier_route(supplier_id):
    delete_supplier(supplier_id)
    flash("Fornecedor excluído.", "success")
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
        upsert_category(flow_type, name, int(cat_id) if cat_id else None)
        flash("Categoria salva.", "success")
    return redirect(url_for("financas.cadastros", sub="categorias"))


@financas_bp.route("/categorias/<int:cat_id>/excluir", methods=["POST"])
def delete_category_route(cat_id):
    delete_category(cat_id)
    flash("Categoria excluída.", "success")
    return redirect(url_for("financas.cadastros", sub="categorias"))


@financas_bp.route("/subcategorias/salvar", methods=["POST"])
def save_subcategory():
    sub_id = request.form.get("id") or None
    category_id = request.form.get("category_id")
    name = request.form.get("name", "").strip()
    if not name or not category_id:
        flash("Categoria e nome da subcategoria são obrigatórios.", "error")
    else:
        upsert_subcategory(int(category_id), name, int(sub_id) if sub_id else None)
        flash("Subcategoria salva.", "success")
    return redirect(url_for("financas.cadastros", sub="categorias"))


@financas_bp.route("/subcategorias/<int:sub_id>/excluir", methods=["POST"])
def delete_subcategory_route(sub_id):
    delete_subcategory(sub_id)
    flash("Subcategoria excluída.", "success")
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
        upsert_bank(data)
        flash("Banco salvo.", "success")
    return redirect(url_for("financas.cadastros", sub="bancos"))


@financas_bp.route("/bancos/<int:bank_id>/excluir", methods=["POST"])
def delete_bank_route(bank_id):
    delete_bank(bank_id)
    flash("Banco excluído.", "success")
    return redirect(url_for("financas.cadastros", sub="bancos"))


# ══════════════════════════════════════════════════════════════════════════
# MOVIMENTAÇÕES / GERENCIAL / DASHBOARDS
# (implementação completa em fase seguinte da migração — rotas já existem
# para não quebrar a navegação entre sub-módulos de Finanças)
# ══════════════════════════════════════════════════════════════════════════

@financas_bp.route("/movimentacoes")
def movimentacoes():
    return render_template("stub.html", title="Finanças — Movimentações", icon="💸")


@financas_bp.route("/gerencial")
def gerencial():
    return render_template("stub.html", title="Finanças — Gerencial", icon="📊")


@financas_bp.route("/dashboards")
def dashboards():
    return render_template("stub.html", title="Finanças — Dashboards", icon="📈")
