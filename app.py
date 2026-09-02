"""
app.py
BK Gestão Pessoal — Application factory (Flask)

Migração v3: Streamlit → Flask + HTML/CSS/JS, hospedado no Railway.
"""

import logging
import os
from datetime import date

from flask import Flask, render_template
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_db_ready = {"ok": False, "checked": False}


def _ensure_db():
    """Roda as migrations uma única vez por processo (idempotente)."""
    if _db_ready["checked"]:
        return _db_ready["ok"]
    try:
        from database.migrations import run_all_migrations
        _db_ready["ok"] = run_all_migrations()
    except Exception as e:
        logger.error(f"Erro nas migrations: {e}")
        _db_ready["ok"] = False
    _db_ready["checked"] = True
    return _db_ready["ok"]


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-troque-em-producao")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["TEMPLATES_AUTO_RELOAD"] = os.getenv("FLASK_DEBUG", "0") == "1"

    # ─── Banco de dados ────────────────────────────────────────────
    db_ok = _ensure_db()
    app.config["DB_OK"] = db_ok

    from utils.helpers import fmt_currency, fmt_date, money_html
    app.jinja_env.filters["brl"] = fmt_currency
    app.jinja_env.filters["brdate"] = fmt_date
    # "money" é global (não filtro) porque devolve HTML com a máscara R$
    # e a classe CSS que pinta negativo de vermelho — usar em todos os
    # quadros/tabelas em vez de {{ valor|brl }} + cor manual no template.
    app.jinja_env.globals["money"] = money_html

    @app.context_processor
    def inject_globals():
        return {
            "db_ok": app.config.get("DB_OK", False),
            "today": date.today(),
            "app_version": "3.0.0",
        }

    # ─── Auth (login único) ────────────────────────────────────────
    from auth import auth_bp, register_auth_guard
    app.register_blueprint(auth_bp)
    register_auth_guard(app)

    # ─── Healthcheck (sem login, usado pelo Railway) ───────────────
    @app.route("/healthz")
    def healthz():
        return {"status": "ok", "db": app.config.get("DB_OK", False)}, 200

    # ─── Módulos ────────────────────────────────────────────────────
    from blueprints.home import home_bp
    app.register_blueprint(home_bp)

    from blueprints.metas import metas_bp
    app.register_blueprint(metas_bp)

    from blueprints.financas import financas_bp
    app.register_blueprint(financas_bp)

    from blueprints.atividades import atividades_bp
    app.register_blueprint(atividades_bp)

    from blueprints.habitos import habitos_bp
    app.register_blueprint(habitos_bp)

    from blueprints.flow import flow_bp
    app.register_blueprint(flow_bp)

    from blueprints.saude import saude_bp
    app.register_blueprint(saude_bp)

    # ─── Digest diário (agendador em processo) ──────────────────────
    if os.getenv("ENABLE_SCHEDULER", "1") == "1" and db_ok:
        try:
            from scripts.send_digest import start_scheduler
            start_scheduler(app)
        except Exception as e:
            logger.warning(f"Não foi possível iniciar o agendador de digest: {e}")

    # ─── Comando manual de teste do digest diário ──────────────────
    @app.cli.command("send-digest")
    def send_digest_command():
        """Dispara o digest diário imediatamente (ignora notification_log)."""
        from scripts.send_digest import send_digest
        result = send_digest(app, force=True)
        print(result)

    # ─── Páginas de erro ─────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        logger.exception("Erro interno")
        return render_template("errors/500.html"), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8501)), debug=os.getenv("FLASK_DEBUG", "0") == "1")
