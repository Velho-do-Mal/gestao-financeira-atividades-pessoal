"""
database/queries.py
Camada de acesso a dados - todas as queries SQL do sistema
"""

import pandas as pd
from datetime import date, datetime, timedelta
from database.connection import execute_query, db_cursor
from typing import Optional
import uuid


# ═══════════════════════════════════════════════════════════════════
# DASHBOARD / HOME
# ═══════════════════════════════════════════════════════════════════

def get_home_summary():
    """Retorna indicadores para o painel Home."""
    today = date.today()
    in_3_days = today + timedelta(days=3)

    rows = execute_query("""
        SELECT
            COALESCE(SUM(CASE WHEN flow_type='Saída' AND status='Não pago' AND due_date < CURRENT_DATE THEN total_value END), 0) AS overdue,
            COALESCE(SUM(CASE WHEN flow_type='Saída' AND status='Não pago' AND due_date BETWEEN CURRENT_DATE AND CURRENT_DATE+3 THEN total_value END), 0) AS due_soon,
            COALESCE(SUM(CASE WHEN flow_type='Entrada' AND status='Não pago' THEN total_value END), 0) AS receivable,
            COALESCE(SUM(CASE WHEN flow_type='Entrada' AND status='Pago' AND payment_date = CURRENT_DATE THEN total_value END), 0) AS income_today,
            COALESCE(SUM(CASE WHEN flow_type='Saída' AND status='Pago' AND payment_date = CURRENT_DATE THEN total_value END), 0) AS expense_today
        FROM transactions
    """)
    r = dict(rows[0]) if rows else {}
    r['balance_today'] = r.get('income_today', 0) - r.get('expense_today', 0)
    return r


def get_cashflow_chart_data(months: int = 6):
    """Dados do gráfico de barras + linha para os últimos N meses."""
    rows = execute_query("""
        SELECT
            DATE_TRUNC('month', due_date)::date AS month,
            SUM(CASE WHEN flow_type='Entrada' AND status='Pago' THEN total_value ELSE 0 END) AS income,
            SUM(CASE WHEN flow_type='Saída' AND status='Pago' THEN total_value ELSE 0 END) AS expense
        FROM transactions
        WHERE due_date >= DATE_TRUNC('month', NOW() - INTERVAL '%s months')
        GROUP BY 1
        ORDER BY 1
    """, (months,))
    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=['month', 'income', 'expense'])
    if not df.empty:
        df['balance'] = df['income'] - df['expense']
        df['accumulated'] = df['balance'].cumsum()
    return df


def get_today_activities():
    """Atividades que vencem hoje, ordenadas por prioridade."""
    priority_order = """
        CASE priority
            WHEN 'Urgente-Urgente' THEN 1
            WHEN 'Importante-Urgente' THEN 2
            WHEN 'Importante não Urgente' THEN 3
            WHEN 'Não importante-Não urgente' THEN 4
        END
    """
    rows = execute_query(f"""
        SELECT id, title, priority, status, end_date, parent_id
        FROM activities
        WHERE end_date = CURRENT_DATE AND status != 'Concluído'
        ORDER BY {priority_order}, title
    """)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════
# FORNECEDORES
# ═══════════════════════════════════════════════════════════════════

def get_suppliers():
    rows = execute_query("SELECT * FROM suppliers WHERE active=TRUE ORDER BY name")
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def upsert_supplier(data: dict):
    if data.get('id'):
        execute_query("""
            UPDATE suppliers SET name=%s, document=%s, email=%s, phone=%s, address=%s, notes=%s,
            updated_at=NOW() WHERE id=%s
        """, (data['name'], data.get('document'), data.get('email'), data.get('phone'),
               data.get('address'), data.get('notes'), data['id']), fetch=False)
    else:
        execute_query("""
            INSERT INTO suppliers (name, document, email, phone, address, notes)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (data['name'], data.get('document'), data.get('email'), data.get('phone'),
               data.get('address'), data.get('notes')), fetch=False)


def delete_supplier(supplier_id: int):
    execute_query("UPDATE suppliers SET active=FALSE WHERE id=%s", (supplier_id,), fetch=False)


# ═══════════════════════════════════════════════════════════════════
# CATEGORIAS / SUBCATEGORIAS
# ═══════════════════════════════════════════════════════════════════

def get_categories(flow_type: Optional[str] = None):
    if flow_type and flow_type != 'Todos':
        rows = execute_query("""
            SELECT * FROM categories WHERE active=TRUE
            AND (flow_type=%s OR flow_type='Ambos') ORDER BY name
        """, (flow_type,))
    else:
        rows = execute_query("SELECT * FROM categories WHERE active=TRUE ORDER BY flow_type, name")
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def get_subcategories(category_id: int):
    rows = execute_query("""
        SELECT * FROM subcategories WHERE category_id=%s AND active=TRUE ORDER BY name
    """, (category_id,))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def upsert_category(flow_type: str, name: str, cat_id: int = None):
    if cat_id:
        execute_query("UPDATE categories SET flow_type=%s, name=%s WHERE id=%s",
                      (flow_type, name, cat_id), fetch=False)
    else:
        execute_query("INSERT INTO categories (flow_type, name) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                      (flow_type, name), fetch=False)


def upsert_subcategory(category_id: int, name: str, sub_id: int = None):
    if sub_id:
        execute_query("UPDATE subcategories SET name=%s WHERE id=%s", (name, sub_id), fetch=False)
    else:
        execute_query("INSERT INTO subcategories (category_id, name) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                      (category_id, name), fetch=False)


def delete_category(cat_id: int):
    execute_query("UPDATE categories SET active=FALSE WHERE id=%s", (cat_id,), fetch=False)


def delete_subcategory(sub_id: int):
    execute_query("UPDATE subcategories SET active=FALSE WHERE id=%s", (sub_id,), fetch=False)


# ═══════════════════════════════════════════════════════════════════
# BANCOS
# ═══════════════════════════════════════════════════════════════════

def get_banks():
    rows = execute_query("SELECT * FROM banks WHERE active=TRUE ORDER BY name")
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def get_total_initial_balance():
    rows = execute_query("SELECT COALESCE(SUM(initial_balance),0) AS total FROM banks WHERE active=TRUE")
    return float(rows[0]['total']) if rows else 0.0


def upsert_bank(data: dict):
    if data.get('id'):
        execute_query("""
            UPDATE banks SET name=%s, account=%s, agency=%s, initial_balance=%s WHERE id=%s
        """, (data['name'], data.get('account'), data.get('agency'), data.get('initial_balance', 0), data['id']),
                      fetch=False)
    else:
        execute_query("""
            INSERT INTO banks (name, account, agency, initial_balance, current_balance)
            VALUES (%s,%s,%s,%s,%s)
        """, (data['name'], data.get('account'), data.get('agency'),
               data.get('initial_balance', 0), data.get('initial_balance', 0)), fetch=False)


def delete_bank(bank_id: int):
    execute_query("UPDATE banks SET active=FALSE WHERE id=%s", (bank_id,), fetch=False)


# ═══════════════════════════════════════════════════════════════════
# MOVIMENTAÇÕES
# ═══════════════════════════════════════════════════════════════════

def get_transactions(start_date=None, end_date=None, status=None, flow_type=None, is_forecast=None):
    conditions = ["1=1"]
    params = []
    if start_date:
        conditions.append("due_date >= %s"); params.append(start_date)
    if end_date:
        conditions.append("due_date <= %s"); params.append(end_date)
    if status and status != 'Todos':
        conditions.append("status = %s"); params.append(status)
    if flow_type and flow_type != 'Todos':
        conditions.append("flow_type = %s"); params.append(flow_type)
    if is_forecast is not None:
        conditions.append("is_forecast = %s"); params.append(is_forecast)

    where = " AND ".join(conditions)
    rows = execute_query(f"""
        SELECT
            t.id, t.flow_type, t.category_id, t.subcategory_id,
            t.supplier_id, t.bank_id, t.description,
            t.value, t.interest, t.total_value,
            t.due_date, t.payment_date, t.status,
            t.is_recurrent, t.recurrence_type, t.recurrence_group_id,
            t.notes, t.is_forecast, t.created_at, t.updated_at,
            c.name AS category_name,
            s.name AS subcategory_name,
            sup.name AS supplier_name,
            b.name AS bank_name
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN subcategories s ON t.subcategory_id = s.id
        LEFT JOIN suppliers sup ON t.supplier_id = sup.id
        LEFT JOIN banks b ON t.bank_id = b.id
        WHERE {where}
        ORDER BY due_date, flow_type
    """, params)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def insert_transaction(data: dict, recurrence_months: int = 0):
    """Insere movimentação, criando recorrências se necessário."""
    group_id = str(uuid.uuid4()) if data.get('is_recurrent') else None

    base_due = data['due_date']
    if isinstance(base_due, str):
        base_due = datetime.strptime(base_due, '%Y-%m-%d').date()

    records = [(data, base_due)]

    if data.get('is_recurrent') and recurrence_months > 0:
        rec_type = data.get('recurrence_type', 'Mensal')
        for i in range(1, recurrence_months + 1):
            next_data = data.copy()
            if rec_type == 'Mensal':
                from dateutil.relativedelta import relativedelta
                next_due = base_due + relativedelta(months=i)
            elif rec_type == 'Diário':
                next_due = base_due + timedelta(days=i)
            elif rec_type == 'Anual':
                from dateutil.relativedelta import relativedelta
                next_due = base_due + relativedelta(years=i)
            records.append((next_data, next_due))

    with db_cursor() as cur:
        for rec_data, due in records:
            cur.execute("""
                INSERT INTO transactions
                (flow_type, category_id, subcategory_id, supplier_id, bank_id,
                 description, value, interest, due_date, status,
                 is_recurrent, recurrence_type, recurrence_group_id, notes, is_forecast)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                rec_data['flow_type'],
                rec_data.get('category_id'),
                rec_data.get('subcategory_id'),
                rec_data.get('supplier_id'),
                rec_data.get('bank_id'),
                rec_data.get('description'),
                rec_data.get('value', 0),
                rec_data.get('interest', 0),
                due,
                rec_data.get('status', 'Não pago'),
                rec_data.get('is_recurrent', False),
                rec_data.get('recurrence_type', 'Mensal'),
                group_id,
                rec_data.get('notes'),
                rec_data.get('is_forecast', True)
            ))


def update_transaction(transaction_id: int, data: dict):
    execute_query("""
        UPDATE transactions SET flow_type=%s, category_id=%s, subcategory_id=%s,
        value=%s, interest=%s, due_date=%s, status=%s, payment_date=%s,
        description=%s, updated_at=NOW() WHERE id=%s
    """, (data['flow_type'], data.get('category_id'), data.get('subcategory_id'),
           data.get('value', 0), data.get('interest', 0), data['due_date'],
           data.get('status', 'Não pago'), data.get('payment_date'),
           data.get('description'), transaction_id), fetch=False)


def delete_transaction(transaction_id: int):
    execute_query("DELETE FROM transactions WHERE id=%s", (transaction_id,), fetch=False)


def get_cashflow_planned_vs_actual(months: int = 24):
    """Retorna dados de previsto x realizado por mês."""
    rows = execute_query("""
        SELECT
            DATE_TRUNC('month', due_date)::date AS month,
            flow_type,
            is_forecast,
            SUM(total_value) AS total
        FROM transactions
        WHERE due_date >= DATE_TRUNC('month', NOW()) - INTERVAL '1 month'
          AND due_date < DATE_TRUNC('month', NOW()) + INTERVAL '%s months'
        GROUP BY 1, 2, 3
        ORDER BY 1, 2
    """, (months,))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════
# METAS
# ═══════════════════════════════════════════════════════════════════

def get_goals():
    rows = execute_query("SELECT * FROM goals ORDER BY time_bound, title")
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def upsert_goal(data: dict):
    if data.get('id'):
        execute_query("""
            UPDATE goals SET title=%s, specific=%s, measurable=%s, achievable=%s,
            relevant=%s, time_bound=%s, target_value=%s, current_value=%s, status=%s
            WHERE id=%s
        """, (data['title'], data.get('specific'), data.get('measurable'), data.get('achievable'),
               data.get('relevant'), data.get('time_bound'), data.get('target_value', 0),
               data.get('current_value', 0), data.get('status', 'Em andamento'), data['id']), fetch=False)
    else:
        execute_query("""
            INSERT INTO goals (title, specific, measurable, achievable, relevant,
            time_bound, target_value, current_value, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (data['title'], data.get('specific'), data.get('measurable'), data.get('achievable'),
               data.get('relevant'), data.get('time_bound'), data.get('target_value', 0),
               data.get('current_value', 0), data.get('status', 'Em andamento')), fetch=False)


def delete_goal(goal_id: int):
    execute_query("DELETE FROM goals WHERE id=%s", (goal_id,), fetch=False)


# ═══════════════════════════════════════════════════════════════════
# ORÇAMENTO
# ═══════════════════════════════════════════════════════════════════

def get_budget(year_month: date):
    rows = execute_query("""
        SELECT b.*, c.name AS category_name, c.flow_type, s.name AS subcategory_name
        FROM budget b
        JOIN categories c ON b.category_id = c.id
        LEFT JOIN subcategories s ON b.subcategory_id = s.id
        WHERE b.year_month = %s
        ORDER BY c.flow_type, c.name, s.name
    """, (year_month,))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def upsert_budget(category_id: int, subcategory_id: Optional[int], year_month: date, planned_value: float):
    execute_query("""
        INSERT INTO budget (category_id, subcategory_id, year_month, planned_value)
        VALUES (%s,%s,%s,%s)
        ON CONFLICT (category_id, subcategory_id, year_month)
        DO UPDATE SET planned_value=%s, updated_at=NOW()
    """, (category_id, subcategory_id, year_month, planned_value, planned_value), fetch=False)


def get_budget_vs_actual(year_month: date):
    """Orçado x Realizado por categoria."""
    rows = execute_query("""
        SELECT c.name AS category, c.flow_type,
               COALESCE(b.planned_value, 0) AS planned,
               COALESCE(SUM(t.total_value), 0) AS actual
        FROM categories c
        LEFT JOIN budget b ON b.category_id = c.id AND b.year_month = %s
        LEFT JOIN transactions t ON t.category_id = c.id
            AND DATE_TRUNC('month', t.due_date) = %s
            AND t.status = 'Pago'
        WHERE c.active = TRUE
        GROUP BY c.name, c.flow_type, b.planned_value
        ORDER BY c.flow_type, c.name
    """, (year_month, year_month))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════
# ATIVIDADES
# ═══════════════════════════════════════════════════════════════════

def get_activities():
    rows = execute_query("""
        SELECT * FROM activities ORDER BY
            COALESCE(parent_id, id), parent_id NULLS FIRST, order_index, title
    """)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def upsert_activity(data: dict):
    if data.get('id'):
        execute_query("""
            UPDATE activities SET title=%s, description=%s, start_date=%s, end_date=%s,
            priority=%s, status=%s, parent_id=%s, updated_at=NOW() WHERE id=%s
        """, (data['title'], data.get('description'), data.get('start_date'), data.get('end_date'),
               data.get('priority', 'Importante não Urgente'), data.get('status', 'Não iniciado'),
               data.get('parent_id'), data['id']), fetch=False)
    else:
        rows = execute_query("""
            INSERT INTO activities (title, description, start_date, end_date, priority, status, parent_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (data['title'], data.get('description'), data.get('start_date'), data.get('end_date'),
               data.get('priority', 'Importante não Urgente'), data.get('status', 'Não iniciado'),
               data.get('parent_id')))
        return rows[0]['id'] if rows else None


def delete_activity(activity_id: int):
    execute_query("DELETE FROM activities WHERE id=%s OR parent_id=%s", (activity_id, activity_id), fetch=False)


# ═══════════════════════════════════════════════════════════════════
# PLANO DE AÇÃO (5W2H)
# ═══════════════════════════════════════════════════════════════════

def get_action_plans():
    rows = execute_query("""
        SELECT ap.*, a.title AS activity_title
        FROM action_plan ap
        LEFT JOIN activities a ON ap.activity_id = a.id
        ORDER BY ap.when_date, ap.id
    """)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def upsert_action_plan(data: dict):
    if data.get('id'):
        execute_query("""
            UPDATE action_plan SET activity_id=%s, what=%s, why=%s, who=%s,
            when_date=%s, where_place=%s, how=%s, how_much=%s, status=%s WHERE id=%s
        """, (data.get('activity_id'), data.get('what'), data.get('why'), data.get('who'),
               data.get('when_date'), data.get('where_place'), data.get('how'),
               data.get('how_much'), data.get('status', 'Pendente'), data['id']), fetch=False)
    else:
        execute_query("""
            INSERT INTO action_plan (activity_id, what, why, who, when_date, where_place, how, how_much, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (data.get('activity_id'), data.get('what'), data.get('why'), data.get('who'),
               data.get('when_date'), data.get('where_place'), data.get('how'),
               data.get('how_much'), data.get('status', 'Pendente')), fetch=False)


def delete_action_plan(plan_id: int):
    execute_query("DELETE FROM action_plan WHERE id=%s", (plan_id,), fetch=False)


# ═══════════════════════════════════════════════════════════════════
# NOTIFICAÇÕES / ALERTAS
# ═══════════════════════════════════════════════════════════════════

def get_items_for_notification():
    """Retorna contas e atividades que vencem nos próximos 3 dias."""
    rows = execute_query("""
        SELECT 'transaction' AS type, description AS title, due_date, flow_type AS extra
        FROM transactions
        WHERE status='Não pago' AND due_date BETWEEN CURRENT_DATE AND CURRENT_DATE+3
        UNION ALL
        SELECT 'activity' AS type, title, end_date AS due_date, priority AS extra
        FROM activities
        WHERE status != 'Concluído' AND end_date BETWEEN CURRENT_DATE AND CURRENT_DATE+3
        ORDER BY due_date
    """)
    return rows or []
