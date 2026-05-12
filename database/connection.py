"""
database/connection.py
Gerenciamento de conexão com PostgreSQL (Neon)

CORREÇÕES v2:
  - Pool de conexões real (ThreadedConnectionPool) em vez de retornar só a URL
  - cursor_factory aplicado por conexão (não no construtor do pool)
  - ⚠️  _NEON_URL mantida visível conforme solicitado — LEMBRETE: atualizar a
    senha após rotacionar no painel do Neon e, antes de publicar, mover para
    .streamlit/secrets.toml
"""

import psycopg2
import psycopg2.pool
import psycopg2.extras
from contextlib import contextmanager
import streamlit as st
import logging

logger = logging.getLogger(__name__)

# ⚠️  TODO — atualizar senha após rotacionar no painel Neon, depois mover para secrets.toml
_NEON_URL = (
    "postgresql://neondb_owner:npg_bDpOXoF4NkJ9"
    "@ep-frosty-fog-aixy8ibt-pooler.c-4.us-east-1.aws.neon.tech"
    "/neondb?sslmode=require&channel_binding=require"
)


def get_db_url() -> str:
    """Retorna URL do banco: secrets.toml → variável de ambiente → fallback hardcoded."""
    try:
        url = st.secrets["database"]["url"]
        if url:
            return url
    except Exception:
        pass
    import os
    url_env = os.getenv("DATABASE_URL", "")
    if url_env:
        return url_env
    return _NEON_URL


@st.cache_resource
def get_connection_pool():
    """
    Pool de conexões reutilizável — uma instância por processo do servidor Streamlit.
    maxconn=5 respeita o limite de conexões do Neon free tier (10 simultâneas).
    """
    url = get_db_url()
    try:
        pool = psycopg2.pool.ThreadedConnectionPool(minconn=1, maxconn=5, dsn=url)
        logger.info("✅ Pool de conexões PostgreSQL criado")
        return pool
    except Exception as e:
        logger.error(f"❌ Falha ao criar pool de conexões: {e}")
        raise


@contextmanager
def db_cursor():
    """
    Context manager para operações no banco.
    Pega conexão do pool, faz commit ou rollback automático, devolve ao pool.
    """
    pool = get_connection_pool()
    conn = pool.getconn()
    try:
        # cursor_factory aplicado por cursor, não no construtor do pool
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cur
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro de banco de dados: {e}")
        raise
    finally:
        cur.close()
        pool.putconn(conn)


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
