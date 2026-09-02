"""
database/migrations_users.py
Multiusuário — tabela `users` + coluna `user_id` em toda tabela de dados
pessoais, com migração aditiva e backfill automático dos dados que já
existiam (todos passam a pertencer ao primeiro usuário/admin).

Estratégia (idempotente, roda a cada start do app):
  1. Cria a tabela `users` se não existir.
  2. Semeia o primeiro usuário (admin) a partir de APP_USERNAME/APP_PASSWORD
     — só se a tabela `users` estiver vazia. É o que mantém o login atual
     funcionando sem qualquer ação manual após o deploy desta mudança.
  3. Para cada tabela de dados pessoais: adiciona a coluna user_id (nullable
     no ALTER), preenche as linhas antigas (user_id IS NULL) com o id do
     primeiro usuário, e só então aplica NOT NULL — sempre reexecutável.

`foods` (base de alimentos) fica de fora de propósito: é referência
nutricional compartilhada entre todos os usuários, não dado pessoal.
"""

import logging
import os

from werkzeug.security import generate_password_hash

from database.connection import db_cursor, execute_query

logger = logging.getLogger(__name__)


USERS_MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id            SERIAL PRIMARY KEY,
        username      VARCHAR(80) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        email         VARCHAR(200),
        full_name     VARCHAR(200),
        is_admin      BOOLEAN DEFAULT FALSE,
        active        BOOLEAN DEFAULT TRUE,
        created_at    TIMESTAMP DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
]


# Tabelas de dados pessoais que ganham user_id. `foods` fica fora (global).
TABLES_WITH_USER_ID = [
    "suppliers", "categories", "subcategories", "banks", "transactions",
    "goals", "goal_progress_log",
    "activities", "action_plan",
    "habits", "habit_cycles", "habit_checks",
    "flow_diary", "flow_sessions",
    "workout_divisions", "exercises", "exercise_sets", "workout_logs",
    "meals", "meal_items", "macro_goals",
    "notification_log",
]


def run_users_migrations():
    """Cria a tabela users e semeia o primeiro admin (idempotente)."""
    try:
        with db_cursor() as cur:
            for m in USERS_MIGRATIONS:
                cur.execute(m)
        logger.info("✅ Migrações Users executadas")
    except Exception as e:
        logger.error(f"❌ Erro migrações Users: {e}")
        raise

    try:
        rows = execute_query("SELECT COUNT(*) AS n FROM users")
        if rows and int(rows[0]["n"]) == 0:
            seed_user = os.getenv("APP_USERNAME", "").strip()
            seed_pass = os.getenv("APP_PASSWORD", "")
            if seed_user and seed_pass:
                execute_query(
                    """
                    INSERT INTO users (username, password_hash, email, full_name, is_admin, active)
                    VALUES (%s, %s, %s, %s, TRUE, TRUE)
                    ON CONFLICT (username) DO NOTHING
                    """,
                    (seed_user, generate_password_hash(seed_pass),
                     os.getenv("EMAIL_RECIPIENTS", "").split(",")[0].strip() or None,
                     seed_user),
                    fetch=False,
                )
                logger.info(f"✅ Usuário admin inicial criado: {seed_user}")
            else:
                logger.warning(
                    "⚠️ Tabela users vazia e APP_USERNAME/APP_PASSWORD não definidos "
                    "— nenhum usuário inicial foi criado. Login ficará bloqueado até "
                    "criar um usuário manualmente."
                )
    except Exception as e:
        logger.error(f"❌ Erro ao semear usuário admin inicial: {e}")
        raise


def _first_user_id() -> int | None:
    rows = execute_query("SELECT id FROM users ORDER BY id LIMIT 1")
    return int(rows[0]["id"]) if rows else None


def run_multi_tenant_migrations():
    """Adiciona user_id a todas as tabelas de dados pessoais, faz backfill
    das linhas antigas para o primeiro usuário e aplica NOT NULL. Roda
    depois de run_users_migrations() (precisa que exista ao menos 1 user)."""
    default_owner_id = _first_user_id()
    if default_owner_id is None:
        logger.warning(
            "⚠️ Nenhum usuário existe ainda — pulando migração multiusuário "
            "(rodará na próxima inicialização, assim que houver um usuário)."
        )
        return

    try:
        with db_cursor() as cur:
            for table in TABLES_WITH_USER_ID:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE")
                cur.execute(f"UPDATE {table} SET user_id = %s WHERE user_id IS NULL", (default_owner_id,))
                cur.execute(f"ALTER TABLE {table} ALTER COLUMN user_id SET NOT NULL")
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_user ON {table}(user_id)")

            # notification_log tinha sent_date UNIQUE (1 digest por dia no
            # total) — com multiusuário, cada usuário precisa poder ter seu
            # próprio registro no mesmo dia, então a unicidade passa a ser
            # por (user_id, sent_date).
            cur.execute("ALTER TABLE notification_log DROP CONSTRAINT IF EXISTS notification_log_sent_date_key")
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'notification_log_user_date_key'
                    ) THEN
                        ALTER TABLE notification_log
                            ADD CONSTRAINT notification_log_user_date_key UNIQUE (user_id, sent_date);
                    END IF;
                END $$;
            """)

            # categories tinha UNIQUE(flow_type, name) global — com
            # multiusuário cada usuário precisa poder ter sua própria
            # "Alimentação"/"Salário"/etc, então a unicidade passa a ser
            # por (user_id, flow_type, name). upsert_category() já faz
            # ON CONFLICT (user_id, flow_type, name).
            cur.execute("ALTER TABLE categories DROP CONSTRAINT IF EXISTS categories_flow_type_name_key")
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'categories_user_flow_name_key'
                    ) THEN
                        ALTER TABLE categories
                            ADD CONSTRAINT categories_user_flow_name_key UNIQUE (user_id, flow_type, name);
                    END IF;
                END $$;
            """)

            # flow_diary tinha entry_date UNIQUE (1 registro de diário por
            # dia, no total) — com multiusuário cada usuário precisa poder
            # ter seu próprio diário no mesmo dia.
            cur.execute("ALTER TABLE flow_diary DROP CONSTRAINT IF EXISTS flow_diary_entry_date_key")
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'flow_diary_user_entry_date_key'
                    ) THEN
                        ALTER TABLE flow_diary
                            ADD CONSTRAINT flow_diary_user_entry_date_key UNIQUE (user_id, entry_date);
                    END IF;
                END $$;
            """)

            # foods.name era UNIQUE globalmente — continua compartilhada
            # entre todos os usuários (não ganha user_id de propósito).
        logger.info(f"✅ Migração multiusuário OK (dados antigos atribuídos ao usuário #{default_owner_id})")
    except Exception as e:
        logger.error(f"❌ Erro na migração multiusuário: {e}")
        raise
