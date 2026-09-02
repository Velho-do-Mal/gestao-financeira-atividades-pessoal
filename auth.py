"""
auth.py
Login multiusuário — cada pessoa tem sua própria conta (username/senha com
hash), e todo dado do app é isolado por usuário (ver database/queries*.py e
database/migrations_users.py). Não existe cadastro público: só um admin
cria novas contas, em /admin/usuarios (ver blueprints/admin.py).

Sessão assinada pelo Flask (SECRET_KEY), cookie HttpOnly, guarda user_id,
username e is_admin.
"""

from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g

from database.queries_users import verify_login, get_user_by_id

auth_bp = Blueprint("auth", __name__)

# Rotas que não exigem login
PUBLIC_ENDPOINTS = {"auth.login", "healthz", "static"}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Acesso restrito ao administrador.", "error")
            return redirect(url_for("home.index"))
        return view(*args, **kwargs)
    return wrapped


def current_user_id() -> int:
    """ID do usuário logado. Só é chamado dentro de rotas protegidas por
    login_required/register_auth_guard, onde session['user_id'] já existe."""
    return session["user_id"]


def register_auth_guard(app):
    """Registra um before_request global que exige login em toda rota,
    exceto as listadas em PUBLIC_ENDPOINTS, e disponibiliza g.user_id /
    g.username / g.is_admin para o resto do request."""

    @app.before_request
    def _require_login():
        if request.endpoint in PUBLIC_ENDPOINTS or request.endpoint is None:
            return None
        user_id = session.get("user_id")
        if not user_id:
            return redirect(url_for("auth.login", next=request.path))
        g.user_id = user_id
        g.username = session.get("username")
        g.is_admin = bool(session.get("is_admin"))
        return None

    @app.context_processor
    def _inject_user():
        return {
            "current_username": session.get("username"),
            "current_is_admin": bool(session.get("is_admin")),
        }


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("home.index"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = verify_login(username, password)
        if user:
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["is_admin"] = bool(user["is_admin"])
            session.permanent = True
            next_url = request.args.get("next") or url_for("home.index")
            return redirect(next_url)
        error = "Usuário ou senha inválidos, ou conta desativada."

    return render_template("auth/login.html", error=error)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
