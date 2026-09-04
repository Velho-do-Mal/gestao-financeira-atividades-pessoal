"""
database/connection.py
Gerenciamento de conexão com PostgreSQL (Neon)

v6 — Pool de conexões (correção de performance)
  - v5 abria e fechava uma conexão TCP+TLS nova a cada query (handshake
    completo até o pooler do Neon em us-east-1). Uma única página como a
    Home dispara 8+ queries independentes — ou seja, 8+ handshakes
    completos e SEQUENCIAIS só para carregar uma tela. Isso é a causa
    raiz da lentidão percebida no app.
  - Agora usamos um `ThreadedConnectionPool` por processo (worker do
    gunicorn), criado uma vez e reaproveitado entre requisições. Cada
    query passa a pegar uma conexão já aberta do pool (getconn/putconn,
    ~instantâneo) em vez de abrir uma nova do zero.
  - Continua sem dependência de `st.secrets` e sem URL hardcoded — vem
    exclusivamente de `DATABASE_URL` (env/.env em dev, Railway Variables
    em produção).
"""

import psycopg2
import psycopg2.extras
import psycopg2.pool
from contextlib import contextmanager
import atexit
import logging
import os
import threading

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Tamanho do pool por processo. Com `gunicorn --workers 2 --threads 4`,
# cada processo pode ter até 4 threads concorrentes pedindo conexão ao
# mesmo tempo — MAXCONN um pouco acima disso dá folga sem exagerar no
# número de conexões abertas no Neon (2 processos x 10 = 20 no máximo).
_POOL_MIN = int(os.getenv("DB_POOL_MIN", "2"))
_POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))

_pool = None
_pool_lock = threading.Lock()


def get_db_url() -> str:
    """Retorna a URL do banco a partir da variável de ambiente DATABASE_URL."""
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError(
            "DATABASE_URL não configurada. Defina em um arquivo .env "
            "(desenvolvimento) ou nas Variables do Railway (produção)."
        )
    return url


def _get_pool():
    """Cria o pool na primeira chamada (lazy, thread-safe) e reaproveita depois."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = psycopg2.pool.ThreadedConnectionPool(
                    _POOL_MIN, _POOL_MAX, get_db_url(), connect_timeout=10
                )
                atexit.register(_close_pool)
                logger.info(f"Pool de conexões criado (min={_POOL_MIN}, max={_POOL_MAX}).")
    return _pool


def _close_pool():
    global _pool
    if _pool is not None:
        try:
            _pool.closeall()
        except Exception:
            pass
        _pool = None


@contextmanager
def db_cursor():
    """
    Context manager para operações no banco.
    Pega uma conexão do pool (getconn) e devolve ao final (putconn) — não
    abre/fecha um socket TCP+TLS novo a cada query como antes.

    Se a conexão que o pool devolveu estiver morta (ex.: Neon fechou por
    inatividade) usamos uma conexão avulsa só para esta operação e
    devolvemos a conexão original ao pool marcada para descarte
    (close=True), para não ficar tentando reusar uma conexão morta depois.

    Pre-ping: `.closed` só reflete o que o psycopg2 sabe *localmente* — se
    o Neon suspender o compute (ou fechar por inatividade) o socket do
    lado do servidor morre, mas a conexão no pool continua marcada como
    aberta até a próxima tentativa de uso falhar. É exatamente esse o
    padrão do bug "Erro interno" reportado: a 1ª requisição depois de um
    tempo sem tráfego pega essa conexão parada, a query estoura
    OperationalError → 500; a 2ª requisição (usuário clica em qualquer
    botão) já pega outra conexão do pool (a morta foi descartada no
    `finally` da 1ª) e funciona normalmente. Para não expor esse erro ao
    usuário, testamos a conexão com um "SELECT 1" barato antes de
    entregá-la — se falhar, descartamos e abrimos uma avulsa na hora, de
    forma transparente para quem chamou (sem gerar 500).
    """
    pool = _get_pool()
    pooled_conn = pool.getconn()  # sempre precisa voltar via putconn no final
    work_conn = pooled_conn
    discard_pooled = False
    cur = None
    try:
        if pooled_conn.closed:
            # Conexão morta (ex.: idle timeout do Neon) — usa uma avulsa
            # só para esta operação e descarta a do pool no final.
            discard_pooled = True
            work_conn = psycopg2.connect(get_db_url(), connect_timeout=10)
        else:
            try:
                with pooled_conn.cursor() as ping_cur:
                    ping_cur.execute("SELECT 1")
            except Exception:
                # Conexão do pool está morta do lado do servidor (Neon
                # suspenso/idle timeout) mas o psycopg2 não sabia —
                # descarta e abre uma avulsa só para esta operação, sem
                # deixar o erro subir para o usuário.
                discard_pooled = True
                try:
                    pooled_conn.rollback()
                except Exception:
                    pass
                work_conn = psycopg2.connect(get_db_url(), connect_timeout=10)
        cur = work_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cur
        work_conn.commit()
    except psycopg2.OperationalError as e:
        # Erro de conexão (não de SQL) — não devolve a conexão do pool boa.
        discard_pooled = True
        try:
            work_conn.rollback()
        except Exception:
            pass
        logger.error(f"Erro de conexão com o banco: {e}")
        raise
    except Exception as e:
        try:
            work_conn.rollback()
        except Exception:
            pass
        logger.error(f"Erro de banco: {e}")
        raise
    finally:
        if cur:
            try:
                cur.close()
            except Exception:
                pass
        if work_conn is not pooled_conn:
            # Conexão avulsa: fecha direto, não é do pool.
            try:
                work_conn.close()
            except Exception:
                pass
        try:
            pool.putconn(pooled_conn, close=discard_pooled)
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
