"""
auth.py
Login único (usuário/senha via variáveis de ambiente) protegendo todo o app.

Não é um sistema de múltiplos usuários — é um portão de acesso simples para
uma aplicação pessoal com dados financeiros, hospedada em uma URL pública no
Railway. Sessão assinada pelo Flask (SECRET_KEY), cookie HttpOnly.
"""

import os
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, session, flash

auth_bp = Blueprint("auth", __name__)

# Rotas que não exigem login
PUBLIC_ENDPOINTS = {"auth.login", "healthz", "static"}


def _check_credentials(username: str, password: str) -> bool:
    expected_user = os.getenv("APP_USERNAME", "")
    expected_pass = os.getenv("APP_PASSWORD", "")
    if not expected_user or not expected_pass:
        # Sem credenciais configuradas — não libera acesso por segurança.
        return False
    return username == expected_user and password == expected_pass


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def register_auth_guard(app):
    """Registra um before_request global que exige login em toda rota,
    exceto as listadas em PUBLIC_ENDPOINTS."""

    @app.before_request
    def _require_login():
        if request.endpoint in PUBLIC_ENDPOINTS or request.endpoint is None:
            return None
        if not session.get("logged_in"):
            return redirect(url_for("auth.login", next=request.path))
        return None


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("home.index"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if _check_credentials(username, password):
            session.clear()
            session["logged_in"] = True
            session["username"] = username
            session.permanent = True
            next_url = request.args.get("next") or url_for("home.index")
            return redirect(next_url)
        error = "Usuário ou senha inválidos."

    return render_template("auth/login.html", error=error)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
