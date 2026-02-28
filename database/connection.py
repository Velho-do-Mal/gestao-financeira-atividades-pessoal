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


def get_db_url() -> str:
    """Retorna a URL do banco de dados das secrets do Streamlit."""
    try:
        return st.secrets["database"]["url"]
    except Exception:
        import os
        return os.getenv("DATABASE_URL", "")


@st.cache_resource
def get_connection_pool():
    """Cria pool de conexões reutilizável."""
    url = get_db_url()
    return url


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
