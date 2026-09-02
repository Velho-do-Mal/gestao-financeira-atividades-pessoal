"""
database/connection.py
Gerenciamento de conexão com PostgreSQL (Neon)

v5 — Migração Streamlit → Flask
  - Removida dependência de `st.secrets` e a URL do banco hardcoded no
    código-fonte (credencial exposta no repositório — corrigido).
  - URL do banco agora vem exclusivamente de variável de ambiente
    `DATABASE_URL` (arquivo .env em desenvolvimento, Railway Variables
    em produção). Sem fallback hardcoded.
  - Mantido o padrão "conexão nova por query" (sem pool local), pois o
    pgBouncer do Neon já gerencia pooling na infraestrutura dele.
"""

import psycopg2
import psycopg2.extras
from contextlib import contextmanager
import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def get_db_url() -> str:
    """Retorna a URL do banco a partir da variável de ambiente DATABASE_URL."""
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError(
            "DATABASE_URL não configurada. Defina em um arquivo .env "
            "(desenvolvimento) ou nas Variables do Railway (produção)."
        )
    return url


def _new_connection():
    """Abre uma conexão nova diretamente (sem pool local)."""
    return psycopg2.connect(get_db_url(), connect_timeout=10)


@contextmanager
def db_cursor():
    """
    Context manager para operações no banco.
    Abre e fecha uma conexão por operação.
    Seguro contra InterfaceError porque nunca reutiliza conexões antigas.
    """
    conn = None
    cur = None
    try:
        conn = _new_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cur
        conn.commit()
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass  # Ignora erro no rollback — conexão já pode estar morta
        logger.error(f"Erro de banco: {e}")
        raise
    finally:
        if cur:
            try:
                cur.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def execute_query(query: str, params=None, fetch: bool = True):
    """Executa query e retorna lista de RealDictRow ou None."""
    with db_cursor() as cur:
        cur.execute(query, params or ())
        if fetch:
            return cur.fetchall()
        return None


def execute_many(query: str, data: list):
    """Executa query com múltiplos registros em batch."""
    with db_cursor() as cur:
        psycopg2.extras.execute_batch(cur, query, data)
