"""
blueprints/home.py
Dashboard principal — implementação completa entra na Fase 3 da migração.
Por enquanto, uma página inicial simples para validar o pipeline de deploy.
"""

from flask import Blueprint, render_template

home_bp = Blueprint("home", __name__)


@home_bp.route("/")
def index():
    return render_template("stub.html", title="Home", icon="🏠")
