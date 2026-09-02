"""
database/queries_digest.py
Queries do digest diário por e-mail (contas vencidas, contas que vencem
hoje e atividades do dia) — módulo independente (não depende de
database/queries.py) para não puxar dependências de outras fases.

MULTIUSUÁRIO: cada usuário recebe seu próprio digest, com apenas os
próprios dados — toda função recebe `user_id` e filtra por ele.
notification_log agora é único por (user_id, sent_date).
"""

from database.connection import execute_query


def get_overdue_transactions(user_id: int):
    """Contas do usuário com vencimento no passado e ainda não pagas."""
    return execute_query(
        """
        SELECT t.id, t.description, t.due_date, t.value, t.flow_type,
               s.name AS supplier_name
        FROM transactions t
        LEFT JOIN suppliers s ON s.id = t.supplier_id
        WHERE t.status = 'Não pago' AND t.due_date < CURRENT_DATE AND t.user_id = %s
        ORDER BY t.due_date ASC
        """,
        (user_id,),
    ) or []


def get_due_today_transactions(user_id: int):
    """Contas do usuário com vencimento hoje e ainda não pagas."""
    return execute_query(
        """
        SELECT t.id, t.description, t.due_date, t.value, t.flow_type,
               s.name AS supplier_name
        FROM transactions t
        LEFT JOIN suppliers s ON s.id = t.supplier_id
        WHERE t.status = 'Não pago' AND t.due_date = CURRENT_DATE AND t.user_id = %s
        ORDER BY t.value DESC
        """,
        (user_id,),
    ) or []


def get_today_activities(user_id: int):
    """Atividades do usuário (inclusive as vinculadas a metas) previstas para
    hoje e ainda não concluídas: hoje está dentro de [start_date, end_date],
    ou end_date é hoje, ou start_date é hoje quando não há end_date."""
    return execute_query(
        """
        SELECT a.id, a.title, a.priority, a.status, a.start_date, a.end_date,
               g.title AS goal_title
        FROM activities a
        LEFT JOIN goals g ON g.id = a.goal_id
        WHERE a.status != 'Concluído' AND a.user_id = %s
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
        """,
        (user_id,),
    ) or []


def was_digest_sent_today(user_id: int) -> bool:
    rows = execute_query(
        "SELECT 1 FROM notification_log WHERE sent_date = CURRENT_DATE AND user_id = %s",
        (user_id,),
    )
    return bool(rows)


def register_digest_sent(user_id: int, overdue_count: int, due_today_count: int, activities_count: int):
    execute_query(
        """
        INSERT INTO notification_log (sent_date, overdue_count, due_today_count, activities_count, user_id)
        VALUES (CURRENT_DATE, %s, %s, %s, %s)
        ON CONFLICT (user_id, sent_date) DO UPDATE
            SET sent_at = NOW(),
                overdue_count = EXCLUDED.overdue_count,
                due_today_count = EXCLUDED.due_today_count,
                activities_count = EXCLUDED.activities_count
        """,
        (overdue_count, due_today_count, activities_count, user_id),
        fetch=False,
    )
