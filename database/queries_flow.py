"""
database/queries_flow.py
Queries do módulo Flow — Sessões de trabalho e Diário

MULTIUSUÁRIO: toda função recebe `user_id` e filtra/estampa esse valor —
cada usuário só vê e só altera o próprio diário e as próprias sessões.
"""

import pandas as pd
from datetime import date, datetime
from database.connection import execute_query


# ══════════════════════════════════════════════════════════════════════════════
# DIÁRIO
# ══════════════════════════════════════════════════════════════════════════════

def get_diary_entry(user_id: int, entry_date: date) -> dict | None:
    rows = execute_query(
        "SELECT * FROM flow_diary WHERE entry_date=%s AND user_id=%s LIMIT 1", (entry_date, user_id)
    )
    return dict(rows[0]) if rows else None


def save_diary_entry(user_id: int, data: dict):
    existing = get_diary_entry(user_id, data['entry_date'])
    if existing:
        execute_query("""
            UPDATE flow_diary
            SET went_well=%s, could_improve=%s, gratitude=%s,
                day_score=%s, notes=%s, updated_at=NOW()
            WHERE entry_date=%s AND user_id=%s
        """, (data.get('went_well'), data.get('could_improve'), data.get('gratitude'),
               data.get('day_score'), data.get('notes'), data['entry_date'], user_id), fetch=False)
    else:
        execute_query("""
            INSERT INTO flow_diary
                (entry_date, went_well, could_improve, gratitude, day_score, notes, user_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (data['entry_date'], data.get('went_well'), data.get('could_improve'),
               data.get('gratitude'), data.get('day_score'), data.get('notes'), user_id),
             fetch=False)


def get_diary_entries(user_id: int, limit: int = 30) -> pd.DataFrame:
    rows = execute_query("""
        SELECT * FROM flow_diary WHERE user_id=%s ORDER BY entry_date DESC LIMIT %s
    """, (user_id, limit))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# SESSÕES DE FLOW
# ══════════════════════════════════════════════════════════════════════════════

def save_flow_session(user_id: int, data: dict):
    execute_query("""
        INSERT INTO flow_sessions
            (session_date, started_at, ended_at, duration_minutes,
             pause_count, pause_minutes, session_score, notes, user_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (data['session_date'], data.get('started_at'), data.get('ended_at'),
           data.get('duration_minutes', 0), data.get('pause_count', 0),
           data.get('pause_minutes', 0), data.get('session_score'),
           data.get('notes'), user_id), fetch=False)


def get_sessions_daily(user_id: int, session_date: date) -> pd.DataFrame:
    rows = execute_query("""
        SELECT * FROM flow_sessions WHERE session_date=%s AND user_id=%s ORDER BY started_at DESC
    """, (session_date, user_id))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def get_sessions_weekly(user_id: int, ref_date: date) -> pd.DataFrame:
    """Retorna sessões da semana que contém ref_date (Seg–Dom)."""
    rows = execute_query("""
        SELECT session_date,
               SUM(duration_minutes)                        AS total_minutes,
               COUNT(*)                                     AS total_sessions,
               ROUND(AVG(session_score)::NUMERIC, 1)        AS avg_score
        FROM flow_sessions
        WHERE session_date >= date_trunc('week', %s::date)
          AND session_date <  date_trunc('week', %s::date) + INTERVAL '7 days'
          AND user_id = %s
        GROUP BY session_date ORDER BY session_date
    """, (ref_date, ref_date, user_id))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def get_sessions_monthly(user_id: int, ref_date: date) -> pd.DataFrame:
    """Retorna sessões do mês de ref_date."""
    rows = execute_query("""
        SELECT session_date,
               SUM(duration_minutes)                        AS total_minutes,
               COUNT(*)                                     AS total_sessions,
               ROUND(AVG(session_score)::NUMERIC, 1)        AS avg_score
        FROM flow_sessions
        WHERE date_trunc('month', session_date) = date_trunc('month', %s::date)
          AND user_id = %s
        GROUP BY session_date ORDER BY session_date
    """, (ref_date, user_id))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def get_flow_summary(user_id: int) -> dict:
    """Totais gerais do usuário: total de horas, sessões, média de score."""
    rows = execute_query("""
        SELECT
            COUNT(*)                                        AS total_sessions,
            COALESCE(SUM(duration_minutes), 0)              AS total_minutes,
            COALESCE(ROUND(AVG(session_score)::NUMERIC,1),0)AS avg_score,
            COALESCE(MAX(duration_minutes), 0)              AS longest_session
        FROM flow_sessions
        WHERE user_id = %s
    """, (user_id,))
    return dict(rows[0]) if rows else {}
