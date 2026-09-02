"""
wsgi.py
Entrypoint usado pelo gunicorn em produção (Railway): `gunicorn wsgi:app`
"""

from app import app

if __name__ == "__main__":
    app.run()
