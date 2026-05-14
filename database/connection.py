"""
database/connection.py
Gerenciamento de conexão com PostgreSQL (Neon)

v4 — Conexão nova por query (sem pool local)
  Motivo: O pgBouncer do Neon gerencia o pooling na infraestrutura dele.
  Usar pool local + pgBouncer causava InterfaceError ao reutilizar conexões
  que o Neon fechou por inatividade, mesmo com keepalives.
  Solução: connect/close por request. O @st.cache_data nas queries garante
  que o banco só é acessado quando o cache expira — não há overhead real.

  ⚠️  _NEON_URL mantida visível conforme solicitado.
"""

import psycopg2
import psycopg2.extras
from contextlib import contextmanager
import streamlit as st
import logging
import os

logger = logging.getLogger(__name__)

# ⚠️  TODO — atualizar senha após rotacionar no painel Neon, depois mover para secrets.toml
_NEON_URL = (
    "postgresql://neondb_owner:npg_bDpOXoF4NkJ9"
    "@ep-frosty-fog-aixy8ibt-pooler.c-4.us-east-1.aws.neon.tech"
    "/neondb?sslmode=require&channel_binding=require"
)


def get_db_url() -> str:
    """Retorna URL do banco: secrets.toml → env var → fallback hardcoded."""
    try:
        url = st.secrets["database"]["url"]
        if url:
            return url
    except Exception:
        pass
    url_env = os.getenv("DATABASE_URL", "")
    if url_env:
        return url_env
    return _NEON_URL


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
    cur  = None
    try:
        conn = _new_connection()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cur
        conn.commit()
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass   # Ignora erro no rollback — conexão já pode estar morta
        logger.error(f"Erro de banco: {e}")
        raise
    finally:
        if cur:
            try: cur.close()
            except Exception: pass
        if conn:
            try: conn.close()
            except Exception: pass


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


# Mantido por compatibilidade com código que chama get_connection_pool()
def get_connection_pool():
    """
    Stub de compatibilidade — não usa mais pool local.
    O Neon gerencia pooling via pgBouncer na infraestrutura.
    """
    return None
