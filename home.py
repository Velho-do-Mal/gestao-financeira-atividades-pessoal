"""
database/migrations.py
Criação e migração de todas as tabelas do sistema BK Finance
"""

from database.connection import db_cursor
import logging

logger = logging.getLogger(__name__)


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
    """
    CREATE TABLE IF NOT EXISTS budget (
        id SERIAL PRIMARY KEY,
        category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
        subcategory_id INTEGER REFERENCES subcategories(id),
        year_month DATE NOT NULL,
        planned_value NUMERIC(15,2) DEFAULT 0,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(category_id, subcategory_id, year_month)
    )
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

    # ─── ÍNDICES ────────────────────────────────────────────────────────────────
    "CREATE INDEX IF NOT EXISTS idx_transactions_due_date ON transactions(due_date)",
    "CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status)",
    "CREATE INDEX IF NOT EXISTS idx_transactions_flow_type ON transactions(flow_type)",
    "CREATE INDEX IF NOT EXISTS idx_activities_end_date ON activities(end_date)",
    "CREATE INDEX IF NOT EXISTS idx_activities_parent ON activities(parent_id)",
]


def run_migrations():
    """Executa todas as migrações pendentes."""
    try:
        with db_cursor() as cur:
            for migration in MIGRATIONS:
                cur.execute(migration)
        logger.info("✅ Migrações executadas com sucesso")
        return True
    except Exception as e:
        logger.error(f"❌ Erro nas migrações: {e}")
        raise e
