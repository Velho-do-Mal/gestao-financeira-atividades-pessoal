"""
database/migrations.py
Criação e migração de todas as tabelas do sistema BK Finance

CORREÇÕES v2:
  - Tabela budget: substituída a constraint UNIQUE(cat, sub, month) por índices
    parciais NULL-safe, corrigindo o bug de múltiplos registros com sub=NULL.
"""

from database.connection import db_cursor, get_db_url
import logging
import psycopg2

logger = logging.getLogger(__name__)

# Lock de migração (pg_advisory_lock) — o Procfile/railway.json sobem o
# Gunicorn com `--workers 2`, e cada worker chama run_all_migrations() na
# própria inicialização (ver app.py). Sem esse lock, os 2 processos rodam
# a migração multiusuário (20 tabelas, ALTER/UPDATE/CREATE INDEX) AO MESMO
# TEMPO contra o mesmo Postgres — isso já causou lock contention real em
# produção (deadlock/timeout num dos workers, deixando esse worker com
# "Banco desconectado" pro resto do processo, e deixando o app geral lento
# enquanto os locks do Postgres ficavam disputados). Com o advisory lock,
# só um worker por vez roda as migrações; o outro espera (até 60s) e, como
# tudo é idempotente, a segunda passada é praticamente instantânea.
_MIGRATION_LOCK_ID = 727181935  # constante arbitrária, só precisa ser igual em todo lugar


MIGRATIONS = [
    # ─── FORNECEDORES ───────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS suppliers (
        id SERIAL PRIMARY KEY,
        name VARCHAR(200) NOT NULL,
        document VARCHAR(20),
        email VARCHAR(150),
        phone VARCHAR(20),
        address TEXT,
        notes TEXT,
        active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )
    """,

    # ─── CATEGORIAS ─────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS categories (
        id SERIAL PRIMARY KEY,
        flow_type VARCHAR(10) NOT NULL CHECK (flow_type IN ('Entrada', 'Saída', 'Ambos')),
        name VARCHAR(100) NOT NULL,
        active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(flow_type, name)
    )
    """,

    # ─── SUBCATEGORIAS ──────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS subcategories (
        id SERIAL PRIMARY KEY,
        category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
        name VARCHAR(100) NOT NULL,
        active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(category_id, name)
    )
    """,

    # ─── BANCOS ─────────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS banks (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        account VARCHAR(30),
        agency VARCHAR(20),
        initial_balance NUMERIC(15,2) DEFAULT 0,
        current_balance NUMERIC(15,2) DEFAULT 0,
        active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """,

    # ─── MOVIMENTAÇÕES ──────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS transactions (
        id SERIAL PRIMARY KEY,
        flow_type VARCHAR(10) NOT NULL CHECK (flow_type IN ('Entrada', 'Saída')),
        category_id INTEGER REFERENCES categories(id),
        subcategory_id INTEGER REFERENCES subcategories(id),
        supplier_id INTEGER REFERENCES suppliers(id),
        bank_id INTEGER REFERENCES banks(id),
        description TEXT,
        value NUMERIC(15,2) NOT NULL DEFAULT 0,
        interest NUMERIC(15,2) DEFAULT 0,
        total_value NUMERIC(15,2) GENERATED ALWAYS AS (value + interest) STORED,
        due_date DATE NOT NULL,
        payment_date DATE,
        status VARCHAR(20) DEFAULT 'Não pago' CHECK (status IN ('Pago', 'Não pago')),
        is_recurrent BOOLEAN DEFAULT FALSE,
        recurrence_type VARCHAR(10) DEFAULT 'Mensal' CHECK (recurrence_type IN ('Diário', 'Mensal', 'Anual')),
        recurrence_group_id UUID,
        notes TEXT,
        is_forecast BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )
    """,

    # ─── METAS (SMART) ──────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS goals (
        id SERIAL PRIMARY KEY,
        title VARCHAR(200) NOT NULL,
        specific TEXT,
        measurable TEXT,
        achievable TEXT,
        relevant TEXT,
        time_bound DATE,
        target_value NUMERIC(15,2),
        current_value NUMERIC(15,2) DEFAULT 0,
        status VARCHAR(20) DEFAULT 'Em andamento' CHECK (status IN ('Em andamento', 'Concluída', 'Cancelada')),
        created_at TIMESTAMP DEFAULT NOW()
    )
    """,

    # ─── ORÇAMENTO ──────────────────────────────────────────────────────────────
    # SEM a UNIQUE constraint na própria tabela — índices parciais abaixo resolvem
    # o problema de NULL != NULL no PostgreSQL (bug corrigido v2).
    """
    CREATE TABLE IF NOT EXISTS budget (
        id SERIAL PRIMARY KEY,
        category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
        subcategory_id INTEGER REFERENCES subcategories(id),
        year_month DATE NOT NULL,
        planned_value NUMERIC(15,2) DEFAULT 0,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )
    """,

    # Índices únicos NULL-safe para budget:
    # PostgreSQL considera NULL != NULL em UNIQUE constraints, então linhas com
    # subcategory_id=NULL não entram em conflito. Índices parciais resolvem isso.
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uniq_budget_no_sub
        ON budget(category_id, year_month)
        WHERE subcategory_id IS NULL
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uniq_budget_with_sub
        ON budget(category_id, subcategory_id, year_month)
        WHERE subcategory_id IS NOT NULL
    """,

    # ─── ATIVIDADES ─────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS activities (
        id SERIAL PRIMARY KEY,
        parent_id INTEGER REFERENCES activities(id) ON DELETE CASCADE,
        title VARCHAR(300) NOT NULL,
        description TEXT,
        start_date DATE,
        end_date DATE,
        priority VARCHAR(40) DEFAULT 'Importante não Urgente'
            CHECK (priority IN (
                'Urgente-Urgente',
                'Importante-Urgente',
                'Importante não Urgente',
                'Não importante-Não urgente'
            )),
        status VARCHAR(20) DEFAULT 'Não iniciado'
            CHECK (status IN ('Concluído', 'Em andamento', 'Não iniciado')),
        order_index INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )
    """,

    # ─── PLANO DE AÇÃO (5W2H) ───────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS action_plan (
        id SERIAL PRIMARY KEY,
        activity_id INTEGER REFERENCES activities(id) ON DELETE CASCADE,
        what TEXT,
        why TEXT,
        who TEXT,
        when_date DATE,
        where_place TEXT,
        how TEXT,
        how_much NUMERIC(15,2),
        status VARCHAR(20) DEFAULT 'Pendente',
        created_at TIMESTAMP DEFAULT NOW()
    )
    """,

    # ─── ÍNDICES DE PERFORMANCE ─────────────────────────────────────────────────
    "CREATE INDEX IF NOT EXISTS idx_transactions_due_date   ON transactions(due_date)",
    "CREATE INDEX IF NOT EXISTS idx_transactions_status     ON transactions(status)",
    "CREATE INDEX IF NOT EXISTS idx_transactions_flow_type  ON transactions(flow_type)",
    "CREATE INDEX IF NOT EXISTS idx_transactions_rec_group  ON transactions(recurrence_group_id)",
    "CREATE INDEX IF NOT EXISTS idx_transactions_bank       ON transactions(bank_id)",
    "CREATE INDEX IF NOT EXISTS idx_transactions_is_forecast ON transactions(is_forecast)",
    "CREATE INDEX IF NOT EXISTS idx_activities_end_date     ON activities(end_date)",
    "CREATE INDEX IF NOT EXISTS idx_activities_parent       ON activities(parent_id)",
]


def run_migrations():
    """Executa todas as migrações/DDL pendentes (idempotente via IF NOT EXISTS)."""
    try:
        with db_cursor() as cur:
            for migration in MIGRATIONS:
                cur.execute(migration)
        logger.info("✅ Migrações executadas com sucesso")
        return True
    except Exception as e:
        logger.error(f"❌ Erro nas migrações: {e}")
        raise


# ─── SAÚDE — MUSCULAÇÃO ─────────────────────────────────────────────────────
HEALTH_MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS workout_divisions (
        id            SERIAL PRIMARY KEY,
        name          VARCHAR(100) NOT NULL,
        day_of_week   VARCHAR(20),
        muscle_groups TEXT,
        order_index   INTEGER DEFAULT 0,
        active        BOOLEAN DEFAULT TRUE,
        created_at    TIMESTAMP DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS exercises (
        id          SERIAL PRIMARY KEY,
        division_id INTEGER NOT NULL REFERENCES workout_divisions(id) ON DELETE CASCADE,
        name        VARCHAR(200) NOT NULL,
        equipment   VARCHAR(100),
        notes       TEXT,
        order_index INTEGER DEFAULT 0,
        active      BOOLEAN DEFAULT TRUE,
        created_at  TIMESTAMP DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS exercise_sets (
        id          SERIAL PRIMARY KEY,
        exercise_id INTEGER NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
        set_number  INTEGER NOT NULL,
        reps        INTEGER,
        weight_kg   NUMERIC(6,2),
        notes       TEXT,
        created_at  TIMESTAMP DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS workout_logs (
        id          SERIAL PRIMARY KEY,
        exercise_id INTEGER NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
        set_number  INTEGER NOT NULL,
        reps_done   INTEGER,
        weight_done NUMERIC(6,2),
        log_date    DATE DEFAULT CURRENT_DATE,
        created_at  TIMESTAMP DEFAULT NOW()
    )
    """,
    # ─── NUTRIÇÃO ────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS foods (
        id          SERIAL PRIMARY KEY,
        name        VARCHAR(200) NOT NULL UNIQUE,
        preparation VARCHAR(50),
        protein_g   NUMERIC(8,2) DEFAULT 0,
        carbs_g     NUMERIC(8,2) DEFAULT 0,
        fat_g       NUMERIC(8,2) DEFAULT 0,
        active      BOOLEAN DEFAULT TRUE,
        created_at  TIMESTAMP DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS meals (
        id        SERIAL PRIMARY KEY,
        name      VARCHAR(100) NOT NULL,
        meal_time TIME,
        meal_date DATE DEFAULT CURRENT_DATE,
        notes     TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS meal_items (
        id         SERIAL PRIMARY KEY,
        meal_id    INTEGER NOT NULL REFERENCES meals(id) ON DELETE CASCADE,
        food_id    INTEGER NOT NULL REFERENCES foods(id),
        quantity_g NUMERIC(8,2) NOT NULL,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS macro_goals (
        id         SERIAL PRIMARY KEY,
        protein_g  NUMERIC(8,2) DEFAULT 150,
        carbs_g    NUMERIC(8,2) DEFAULT 250,
        fat_g      NUMERIC(8,2) DEFAULT 60,
        goal_kcal  NUMERIC(8,2) DEFAULT 2000,
        updated_at TIMESTAMP DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_workout_logs_exercise ON workout_logs(exercise_id, log_date)",
    "CREATE INDEX IF NOT EXISTS idx_meal_items_meal       ON meal_items(meal_id)",
    "CREATE INDEX IF NOT EXISTS idx_meals_date            ON meals(meal_date)",
    "CREATE INDEX IF NOT EXISTS idx_foods_name            ON foods(name)",
]


def run_health_migrations():
    """Executa migrações do módulo Saúde (idempotente)."""
    from database.connection import db_cursor
    import logging
    logger = logging.getLogger(__name__)
    try:
        with db_cursor() as cur:
            for m in HEALTH_MIGRATIONS:
                cur.execute(m)
        logger.info("✅ Migrações Saúde executadas")
    except Exception as e:
        logger.error(f"❌ Erro migrações Saúde: {e}")
        raise


# ─── HÁBITOS — 90 DIAS ──────────────────────────────────────────────────────
HABITS_MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS habits (
        id             SERIAL PRIMARY KEY,
        name           VARCHAR(200) NOT NULL,
        description    TEXT,
        category       VARCHAR(50) DEFAULT 'Geral',
        frequency_type VARCHAR(30) DEFAULT 'Diário',
        frequency_days VARCHAR(50),
        color          VARCHAR(10) DEFAULT '#3B82F6',
        icon           VARCHAR(10) DEFAULT '🎯',
        active         BOOLEAN DEFAULT TRUE,
        created_at     TIMESTAMP DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS habit_cycles (
        id         SERIAL PRIMARY KEY,
        habit_id   INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
        start_date DATE NOT NULL,
        end_date   DATE NOT NULL,
        status     VARCHAR(20) DEFAULT 'Em andamento'
                   CHECK (status IN ('Em andamento','Concluído','Abandonado')),
        created_at TIMESTAMP DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS habit_checks (
        id         SERIAL PRIMARY KEY,
        cycle_id   INTEGER NOT NULL REFERENCES habit_cycles(id) ON DELETE CASCADE,
        check_date DATE NOT NULL,
        done       BOOLEAN DEFAULT TRUE,
        notes      TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(cycle_id, check_date)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_habit_cycles_habit  ON habit_cycles(habit_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_habit_checks_cycle  ON habit_checks(cycle_id, check_date)",
    "CREATE INDEX IF NOT EXISTS idx_habit_checks_date   ON habit_checks(check_date)",
]


def run_habits_migrations():
    """Executa migrações do módulo Hábitos (idempotente)."""
    from database.connection import db_cursor
    import logging
    logger = logging.getLogger(__name__)
    try:
        with db_cursor() as cur:
            for m in HABITS_MIGRATIONS:
                cur.execute(m)
        logger.info("✅ Migrações Hábitos executadas")
    except Exception as e:
        logger.error(f"❌ Erro migrações Hábitos: {e}")
        raise


# ─── FLOW ────────────────────────────────────────────────────────────────────
FLOW_MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS flow_diary (
        id            SERIAL PRIMARY KEY,
        entry_date    DATE UNIQUE NOT NULL,
        went_well     TEXT,
        could_improve TEXT,
        gratitude     TEXT,
        day_score     INTEGER CHECK (day_score BETWEEN 1 AND 10),
        notes         TEXT,
        created_at    TIMESTAMP DEFAULT NOW(),
        updated_at    TIMESTAMP DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS flow_sessions (
        id               SERIAL PRIMARY KEY,
        session_date     DATE NOT NULL,
        started_at       TIMESTAMP,
        ended_at         TIMESTAMP,
        duration_minutes INTEGER DEFAULT 0,
        pause_count      INTEGER DEFAULT 0,
        pause_minutes    INTEGER DEFAULT 0,
        session_score    INTEGER CHECK (session_score BETWEEN 1 AND 10),
        notes            TEXT,
        created_at       TIMESTAMP DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_flow_diary_date    ON flow_diary(entry_date)",
    "CREATE INDEX IF NOT EXISTS idx_flow_sessions_date ON flow_sessions(session_date)",
]


def run_flow_migrations():
    """Executa migrações do módulo Flow (idempotente)."""
    from database.connection import db_cursor
    import logging
    logger = logging.getLogger(__name__)
    try:
        with db_cursor() as cur:
            for m in FLOW_MIGRATIONS:
                cur.execute(m)
        logger.info("✅ Migrações Flow executadas")
    except Exception as e:
        logger.error(f"❌ Erro migrações Flow: {e}")
        raise


# ─── CALENDÁRIO — novos campos em activities ─────────────────────────────────
CALENDAR_MIGRATIONS = [
    "ALTER TABLE activities ADD COLUMN IF NOT EXISTS start_time          TIME",
    "ALTER TABLE activities ADD COLUMN IF NOT EXISTS end_time            TIME",
    "ALTER TABLE activities ADD COLUMN IF NOT EXISTS event_color         VARCHAR(10) DEFAULT '#3B82F6'",
    "ALTER TABLE activities ADD COLUMN IF NOT EXISTS event_type          VARCHAR(50) DEFAULT 'Tarefa'",
    "ALTER TABLE activities ADD COLUMN IF NOT EXISTS recurrence_group_id UUID",
    "CREATE INDEX IF NOT EXISTS idx_activities_start_date    ON activities(start_date)",
    "CREATE INDEX IF NOT EXISTS idx_activities_rec_group     ON activities(recurrence_group_id)",
]


def run_calendar_migrations():
    from database.connection import db_cursor
    import logging
    logger = logging.getLogger(__name__)
    try:
        with db_cursor() as cur:
            for m in CALENDAR_MIGRATIONS:
                cur.execute(m)
        logger.info("✅ Migrações Calendário executadas")
    except Exception as e:
        logger.error(f"❌ Erro migrações Calendário: {e}")
        raise



# ─── METAS (módulo separado) — colunas extras + tabelas de apoio ────────────
GOALS_MIGRATIONS = [
    # Unidade de exibição da meta (ex.: "R$", "%", "clientes", "un.")
    "ALTER TABLE goals ADD COLUMN IF NOT EXISTS unit VARCHAR(20) DEFAULT 'un.'",
    "ALTER TABLE goals ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()",

    # Vínculo de atividades (plano de ação) a uma meta. Reaproveita 100% a
    # tabela `activities` (e por consequência `action_plan`/5W2H) já usada
    # pelo módulo Atividades — cada "serviço" do plano de ação de uma meta
    # é uma activity com goal_id preenchido.
    "ALTER TABLE activities ADD COLUMN IF NOT EXISTS goal_id INTEGER REFERENCES goals(id) ON DELETE SET NULL",
    "CREATE INDEX IF NOT EXISTS idx_activities_goal ON activities(goal_id)",

    # Histórico de check-ins de avanço da meta — permite acompanhar e marcar
    # o progresso ao longo do tempo (não só editar um valor fixo).
    """
    CREATE TABLE IF NOT EXISTS goal_progress_log (
        id SERIAL PRIMARY KEY,
        goal_id INTEGER NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
        log_date DATE NOT NULL DEFAULT CURRENT_DATE,
        value NUMERIC(15,2) NOT NULL,
        note TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_goal_progress_goal ON goal_progress_log(goal_id)",
    "CREATE INDEX IF NOT EXISTS idx_goal_progress_date ON goal_progress_log(log_date)",
]


def run_goals_migrations():
    """Executa migrações do módulo Metas (idempotente)."""
    try:
        with db_cursor() as cur:
            for m in GOALS_MIGRATIONS:
                cur.execute(m)
        logger.info("✅ Migrações Metas executadas")
    except Exception as e:
        logger.error(f"❌ Erro migrações Metas: {e}")
        raise


# ─── NOTIFICAÇÕES — controle do digest diário por e-mail ────────────────────
NOTIFICATIONS_MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS notification_log (
        id SERIAL PRIMARY KEY,
        sent_date DATE NOT NULL UNIQUE,
        sent_at TIMESTAMP DEFAULT NOW(),
        overdue_count INTEGER DEFAULT 0,
        due_today_count INTEGER DEFAULT 0,
        activities_count INTEGER DEFAULT 0
    )
    """,
]


def run_notifications_migrations():
    """Executa migrações de notificações (idempotente)."""
    try:
        with db_cursor() as cur:
            for m in NOTIFICATIONS_MIGRATIONS:
                cur.execute(m)
        logger.info("✅ Migrações Notificações executadas")
    except Exception as e:
        logger.error(f"❌ Erro migrações Notificações: {e}")
        raise


# ─── FUNÇÃO UNIFICADA ────────────────────────────────────────────────────────
def run_all_migrations():
    """
    Executa TODAS as migrations — idempotente (IF NOT EXISTS em tudo).
    Chamada uma vez na inicialização do app, em CADA worker do Gunicorn
    (ver app.py create_app()) — por isso serializa com um advisory lock do
    Postgres antes de rodar: só um worker mexe no schema por vez, os
    outros esperam (a segunda passada de cada um é rápida, pois tudo é
    idempotente).
    """
    lock_conn = None
    got_lock = False
    try:
        lock_conn = psycopg2.connect(get_db_url(), connect_timeout=10)
        lock_conn.autocommit = True
        with lock_conn.cursor() as cur:
            cur.execute("SET lock_timeout = '60s'")
            try:
                cur.execute("SELECT pg_advisory_lock(%s)", (_MIGRATION_LOCK_ID,))
                got_lock = True
            except psycopg2.errors.LockNotAvailable:
                logger.warning(
                    "⚠️ Não consegui pegar o lock de migração em 60s (outro worker "
                    "deve estar migrando) — seguindo mesmo assim, com risco de "
                    "corrida entre workers."
                )
    except Exception as e:
        logger.warning(f"⚠️ Não consegui abrir conexão para o lock de migração: {e} — seguindo sem lock.")

    try:
        # 0. Usuários (precisa existir antes do backfill multiusuário lá no fim)
        from database.migrations_users import run_users_migrations
        run_users_migrations()

        # 1. Schema base (transactions, activities, categories...)
        run_migrations()

        # 2. Saúde
        run_health_migrations()

        # 3. Hábitos
        run_habits_migrations()

        # 4. Flow
        run_flow_migrations()

        # 5. Calendário (colunas extras em activities)
        run_calendar_migrations()

        # 6. Metas (módulo separado)
        run_goals_migrations()

        # 7. Notificações (digest diário)
        run_notifications_migrations()

        # 8. Multiusuário — user_id em todas as tabelas de dados pessoais,
        # com backfill dos dados que já existiam (precisa rodar por último,
        # depois que todas as tabelas acima já existem).
        from database.migrations_users import run_multi_tenant_migrations
        run_multi_tenant_migrations()

        logger.info("✅ Todas as migrations OK")
        return True
    except Exception as e:
        logger.error(f"❌ run_all_migrations falhou: {e}")
        return False
    finally:
        if lock_conn is not None:
            try:
                if got_lock:
                    with lock_conn.cursor() as cur:
                        cur.execute("SELECT pg_advisory_unlock(%s)", (_MIGRATION_LOCK_ID,))
            finally:
                lock_conn.close()
