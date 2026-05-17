"""
database/queries_habitos.py
Queries do módulo Hábitos — Ciclos de 90 dias
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from database.connection import execute_query, db_cursor


# ══════════════════════════════════════════════════════════════════════════════
# HÁBITOS
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=120, show_spinner=False)
def get_habits() -> pd.DataFrame:
    rows = execute_query("""
        SELECT * FROM habits WHERE active = TRUE ORDER BY category, name
    """)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def upsert_habit(data: dict):
    if data.get('id'):
        execute_query("""
            UPDATE habits
            SET name=%s, description=%s, category=%s, frequency_type=%s,
                frequency_days=%s, color=%s, icon=%s
            WHERE id=%s
        """, (data['name'], data.get('description'), data.get('category', 'Geral'),
              data.get('frequency_type', 'Diário'), data.get('frequency_days'),
              data.get('color', '#3B82F6'), data.get('icon', '🎯'), data['id']),
             fetch=False)
    else:
        rows = execute_query("""
            INSERT INTO habits (name, description, category, frequency_type, frequency_days, color, icon)
            VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (data['name'], data.get('description'), data.get('category', 'Geral'),
              data.get('frequency_type', 'Diário'), data.get('frequency_days'),
              data.get('color', '#3B82F6'), data.get('icon', '🎯')))
        return rows[0]['id'] if rows else None


def delete_habit(habit_id: int):
    execute_query("UPDATE habits SET active=FALSE WHERE id=%s", (habit_id,), fetch=False)


# ══════════════════════════════════════════════════════════════════════════════
# CICLOS DE 90 DIAS
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=60, show_spinner=False)
def get_cycles(habit_id: int) -> pd.DataFrame:
    rows = execute_query("""
        SELECT * FROM habit_cycles WHERE habit_id=%s ORDER BY start_date DESC
    """, (habit_id,))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


@st.cache_data(ttl=60, show_spinner=False)
def get_active_cycle(habit_id: int) -> dict | None:
    """Retorna o ciclo ativo mais recente do hábito."""
    rows = execute_query("""
        SELECT * FROM habit_cycles
        WHERE habit_id=%s AND status='Em andamento'
        ORDER BY start_date DESC LIMIT 1
    """, (habit_id,))
    return dict(rows[0]) if rows else None


def start_cycle(habit_id: int, start_date: date) -> int:
    """Inicia novo ciclo de 90 dias. Finaliza ciclos anteriores em andamento."""
    execute_query("""
        UPDATE habit_cycles SET status='Abandonado'
        WHERE habit_id=%s AND status='Em andamento'
    """, (habit_id,), fetch=False)
    end_date = start_date + timedelta(days=89)
    rows = execute_query("""
        INSERT INTO habit_cycles (habit_id, start_date, end_date)
        VALUES (%s,%s,%s) RETURNING id
    """, (habit_id, start_date, end_date))
    return rows[0]['id'] if rows else None


def finish_cycle(cycle_id: int, status: str = 'Concluído'):
    execute_query(
        "UPDATE habit_cycles SET status=%s WHERE id=%s",
        (status, cycle_id), fetch=False,
    )


# ══════════════════════════════════════════════════════════════════════════════
# CHECKS DIÁRIOS
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=30, show_spinner=False)
def get_checks(cycle_id: int) -> pd.DataFrame:
    rows = execute_query("""
        SELECT * FROM habit_checks WHERE cycle_id=%s ORDER BY check_date
    """, (cycle_id,))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def toggle_check(cycle_id: int, check_date: date, notes: str = None):
    """Alterna marcação do dia: se existe marca como feito, se feito desmarca, se não existe cria."""
    existing = execute_query("""
        SELECT id, done FROM habit_checks WHERE cycle_id=%s AND check_date=%s
    """, (cycle_id, check_date))

    if existing:
        new_done = not bool(existing[0]['done'])
        execute_query("""
            UPDATE habit_checks SET done=%s, notes=%s WHERE id=%s
        """, (new_done, notes, existing[0]['id']), fetch=False)
    else:
        execute_query("""
            INSERT INTO habit_checks (cycle_id, check_date, done, notes)
            VALUES (%s,%s,TRUE,%s)
        """, (cycle_id, check_date, notes), fetch=False)


def mark_check(cycle_id: int, check_date: date, done: bool, notes: str = None):
    """Define explicitamente o estado de um dia."""
    execute_query("""
        INSERT INTO habit_checks (cycle_id, check_date, done, notes)
        VALUES (%s,%s,%s,%s)
        ON CONFLICT (cycle_id, check_date)
        DO UPDATE SET done=%s, notes=%s
    """, (cycle_id, check_date, done, notes, done, notes), fetch=False)


@st.cache_data(ttl=30, show_spinner=False)
def get_today_habits() -> pd.DataFrame:
    """Retorna todos os hábitos com ciclo ativo e status de hoje."""
    today = date.today()
    rows = execute_query("""
        SELECT
            h.id AS habit_id, h.name, h.icon, h.color, h.category,
            h.frequency_type, h.frequency_days,
            hc.id AS cycle_id, hc.start_date, hc.end_date,
            COALESCE(ck.done, FALSE) AS done_today,
            ck.id AS check_id
        FROM habits h
        JOIN habit_cycles hc ON hc.habit_id = h.id AND hc.status = 'Em andamento'
        LEFT JOIN habit_checks ck ON ck.cycle_id = hc.id AND ck.check_date = %s
        WHERE h.active = TRUE
        ORDER BY h.category, h.name
    """, (today,))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# ESTATÍSTICAS DO CICLO
# ══════════════════════════════════════════════════════════════════════════════

def calculate_stats(cycle: dict, df_checks: pd.DataFrame, habit: dict) -> dict:
    """
    Calcula todas as estatísticas de um ciclo.
    Retorna: total_programmed, done, pct_done, pct_missed,
             current_streak, best_streak, days_remaining, days_elapsed
    """
    today        = date.today()
    start        = cycle['start_date']
    end          = cycle['end_date']
    if isinstance(start, str): start = date.fromisoformat(str(start))
    if isinstance(end,   str): end   = date.fromisoformat(str(end))
    effective_end = min(end, today)
    freq_type    = habit.get('frequency_type', 'Diário')
    freq_days    = habit.get('frequency_days', '')

    # Dict de checks por data
    checks_by_date = {}
    if not df_checks.empty and 'check_date' in df_checks.columns:
        for _, row in df_checks.iterrows():
            d = row['check_date']
            if hasattr(d, 'date'): d = d.date()
            checks_by_date[d] = bool(row.get('done', False))

    # Dias programados até hoje
    total_programmed = _count_programmed_days(start, effective_end, freq_type, freq_days)

    # Feitos
    done_count = sum(1 for d, v in checks_by_date.items()
                     if v and start <= d <= effective_end)

    pct_done   = round(done_count / total_programmed * 100, 1) if total_programmed > 0 else 0
    pct_missed = round(100 - pct_done, 1)

    # Streak atual (dias consecutivos até hoje)
    current_streak = 0
    d = today
    while d >= start:
        if _is_scheduled(d, freq_type, freq_days):
            if checks_by_date.get(d, False):
                current_streak += 1
            else:
                break
        d -= timedelta(days=1)

    # Melhor streak do ciclo
    best_streak  = 0
    temp_streak  = 0
    for i in range((effective_end - start).days + 1):
        d = start + timedelta(days=i)
        if _is_scheduled(d, freq_type, freq_days):
            if checks_by_date.get(d, False):
                temp_streak += 1
                best_streak = max(best_streak, temp_streak)
            else:
                temp_streak = 0

    days_elapsed   = max(0, (today - start).days + 1)
    days_remaining = max(0, (end - today).days)
    progress_pct   = min(100, round(days_elapsed / 90 * 100))

    return {
        'total_programmed': total_programmed,
        'done':             done_count,
        'pct_done':         pct_done,
        'pct_missed':       pct_missed,
        'current_streak':   current_streak,
        'best_streak':      best_streak,
        'days_elapsed':     days_elapsed,
        'days_remaining':   days_remaining,
        'progress_pct':     progress_pct,
    }


def _count_programmed_days(start: date, end: date, freq_type: str, freq_days: str) -> int:
    if freq_type == 'Diário':
        return max(0, (end - start).days + 1)
    elif freq_type == 'Dias da semana':
        target = _parse_weekdays(freq_days)
        return sum(1 for i in range((end - start).days + 1)
                   if (start + timedelta(days=i)).weekday() in target)
    elif freq_type == 'X vezes por semana':
        try:
            x = int(freq_days or '3')
        except ValueError:
            x = 3
        weeks = max(1, ((end - start).days + 1) // 7)
        return weeks * x
    return (end - start).days + 1


def _is_scheduled(d: date, freq_type: str, freq_days: str,
                  done_this_week: int = 0) -> bool:
    """
    Verifica se o hábito deve ser executado no dia d.
    done_this_week: quantas vezes já foi feito esta semana (usado para X vezes/semana).
    """
    if freq_type is None or freq_type == 'Diário':
        return True
    elif freq_type == 'Dias da semana':
        return d.weekday() in _parse_weekdays(freq_days)
    elif freq_type == 'X vezes por semana':
        # Só mostra se a meta semanal ainda não foi atingida
        try:
            target = int(freq_days or '3')
        except (ValueError, TypeError):
            target = 3
        return done_this_week < target
    return True


def _parse_weekdays(freq_days: str) -> list:
    try:
        return [int(x) for x in str(freq_days or '0,1,2,3,4').split(',')]
    except Exception:
        return [0, 1, 2, 3, 4]
