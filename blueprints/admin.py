"""
blueprints/admin.py
Administração de usuários — restrito a is_admin. Não existe cadastro
público: só um admin cria novas contas por aqui.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash

from auth import admin_required
from database.queries_users import (
    get_all_users, create_user, set_user_active, update_user_password,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/usuarios")
@admin_required
def users():
    return render_template("admin/users.html", users=get_all_users())


@admin_bp.route("/usuarios/novo", methods=["POST"])
@admin_required
def create():
    try:
        create_user(
            username=request.form.get("username", ""),
            password=request.form.get("password", ""),
            email=request.form.get("email", "").strip() or None,
            full_name=request.form.get("full_name", "").strip() or None,
            is_admin=bool(request.form.get("is_admin")),
        )
        flash("Usuário criado.", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.users"))


@admin_bp.route("/usuarios/<int:user_id>/ativar", methods=["POST"])
@admin_required
def toggle_active(user_id):
    active = request.form.get("active") == "1"
    set_user_active(user_id, active)
    flash("Usuário atualizado.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/usuarios/<int:user_id>/senha", methods=["POST"])
@admin_required
def reset_password(user_id):
    try:
        update_user_password(user_id, request.form.get("password", ""))
        flash("Senha redefinida.", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.users"))
