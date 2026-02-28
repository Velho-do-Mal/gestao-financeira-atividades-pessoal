"""
database/connection.py
Gerenciamento de conexão com PostgreSQL (Neon)
"""

import streamlit as st
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

# URL padrão Neon — usada quando secrets.toml não está presente
_NEON_URL = (
    "postgresql://neondb_owner:npg_bDpOXoF4NkJ9"
    "@ep-frosty-fog-aixy8ibt-pooler.c-4.us-east-1.aws.neon.tech"
    "/neondb?sslmode=require&channel_binding=require"
)


def get_db_url() -> str:
    """Retorna a URL do banco: secrets.toml → variável de ambiente → URL Neon embutida."""
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
    """Cria pool de conexões reutilizável."""
    return get_db_url()


def get_connection():
    """Retorna conexão com o banco de dados."""
    url = get_db_url()
    conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn


@contextmanager
def db_cursor():
    """Context manager para operações no banco com commit/rollback automático."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro de banco de dados: {e}")
        raise e
    finally:
        cur.close()
        conn.close()


def execute_query(query: str, params=None, fetch=True):
    """Executa query e retorna resultados."""
    with db_cursor() as cur:
        cur.execute(query, params or ())
        if fetch:
            return cur.fetchall()
        return None


def execute_many(query: str, data: list):
    """Executa query com múltiplos registros."""
    with db_cursor() as cur:
        psycopg2.extras.execute_batch(cur, query, data)
