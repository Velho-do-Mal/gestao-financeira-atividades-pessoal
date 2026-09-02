"""
blueprints/_stub.py
Helper para criar um blueprint "em construção" — usado pelos módulos que
ainda não foram portados de Streamlit para Flask nesta fase da migração.
Cada módulo é substituído por sua implementação real em fases seguintes.
"""

from flask import Blueprint, render_template


def make_stub_blueprint(name: str, url_prefix: str, title: str, icon: str):
    bp = Blueprint(name, __name__, url_prefix=url_prefix)

    @bp.route("/")
    def index():
        return render_template("stub.html", title=title, icon=icon)

    return bp
