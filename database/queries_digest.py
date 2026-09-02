"""
database/queries_digest.py
Queries do digest diário por e-mail (contas vencidas, contas que vencem
hoje e atividades do dia) — módulo independente (não depende de
database/queries.py) para não puxar dependências de outras fases.
"""

from database.connection import execute_query


def get_overdue_transactions():
    """Contas com vencimento no passado e ainda não pagas."""
    return execute_query(
        """
        SELECT t.id, t.description, t.due_date, t.value, t.flow_type,
               s.name AS supplier_name
        FROM transactions t
        LEFT JOIN suppliers s ON s.id = t.supplier_id
        WHERE t.status = 'Não pago' AND t.due_date < CURRENT_DATE
        ORDER BY t.due_date ASC
        """
    ) or []


def get_due_today_transactions():
    """Contas com vencimento hoje e ainda não pagas."""
    return execute_query(
        """
        SELECT t.id, t.description, t.due_date, t.value, t.flow_type,
               s.name AS supplier_name
        FROM transactions t
        LEFT JOIN suppliers s ON s.id = t.supplier_id
        WHERE t.status = 'Não pago' AND t.due_date = CURRENT_DATE
        ORDER BY t.value DESC
        """
    ) or []


def get_today_activities():
    """Atividades (inclusive as vinculadas a metas) previstas para hoje e
    ainda não concluídas: hoje está dentro de [start_date, end_date], ou
    end_date é hoje, ou start_date é hoje quando não há end_date."""
    return execute_query(
        """
        SELECT a.id, a.title, a.priority, a.status, a.start_date, a.end_date,
               g.title AS goal_title
        FROM activities a
        LEFT JOIN goals g ON g.id = a.goal_id
        WHERE a.status != 'Concluído'
          AND (
                CURRENT_DATE = a.end_date
                OR CURRENT_DATE = a.start_date
                OR (a.start_date IS NOT NULL AND a.end_date IS NOT NULL
                    AND CURRENT_DATE BETWEEN a.start_date AND a.end_date)
              )
        ORDER BY
            CASE a.priority
                WHEN 'Urgente-Urgente' THEN 1
                WHEN 'Importante-Urgente' THEN 2
                WHEN 'Importante não Urgente' THEN 3
                ELSE 4
            END,
            a.end_date NULLS LAST
        """
    ) or []


def was_digest_sent_today() -> bool:
    rows = execute_query(
        "SELECT 1 FROM notification_log WHERE sent_date = CURRENT_DATE"
    )
    return bool(rows)


def register_digest_sent(overdue_count: int, due_today_count: int, activities_count: int):
    execute_query(
        """
        INSERT INTO notification_log (sent_date, overdue_count, due_today_count, activities_count)
        VALUES (CURRENT_DATE, %s, %s, %s)
        ON CONFLICT (sent_date) DO UPDATE
            SET sent_at = NOW(),
                overdue_count = EXCLUDED.overdue_count,
                due_today_count = EXCLUDED.due_today_count,
                activities_count = EXCLUDED.activities_count
        """,
        (overdue_count, due_today_count, activities_count),
        fetch=False,
    )
