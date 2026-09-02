"""
database/queries_metas.py
Camada de acesso a dados do módulo Metas (SMART), independente de
database/queries.py (que ainda depende do Streamlit e será migrado em
fase futura). Reaproveita as tabelas `activities` e `action_plan` já
existentes: cada "serviço" do plano de ação de uma meta é uma linha em
`activities` com `goal_id` preenchido; o 5W2H de uma atividade atrasada
usa a tabela `action_plan` do jeito que já era usado por Atividades.
"""

from datetime import date

from database.connection import execute_query


# ══════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════

def _safe_float(val, default=0.0):
    try:
        if val is None or val == "":
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def goal_progress_pct(goal: dict) -> float:
    target = _safe_float(goal.get("target_value"))
    current = _safe_float(goal.get("current_value"))
    if target <= 0:
        return 100.0 if current > 0 else 0.0
    pct = (current / target) * 100
    return max(0.0, min(100.0, round(pct, 1)))


def goal_situation(goal: dict) -> str:
    """Retorna 'concluida' | 'cancelada' | 'atrasada' | 'proximo_prazo' | 'em_dia'."""
    status = goal.get("status")
    if status == "Concluída":
        return "concluida"
    if status == "Cancelada":
        return "cancelada"
    tb = goal.get("time_bound")
    if tb:
        if isinstance(tb, str):
            from datetime import datetime as _dt
            tb = _dt.strptime(tb, "%Y-%m-%d").date()
        today = date.today()
        if tb < today:
            return "atrasada"
        if (tb - today).days <= 30:
            return "proximo_prazo"
    return "em_dia"


def activity_is_late(activity: dict) -> bool:
    if activity.get("status") == "Concluído":
        return False
    end_date = activity.get("end_date")
    if not end_date:
        return False
    if isinstance(end_date, str):
        from datetime import datetime as _dt
        end_date = _dt.strptime(end_date, "%Y-%m-%d").date()
    return end_date < date.today()


# ══════════════════════════════════════════════════════════════════════════
# Metas (goals)
# ══════════════════════════════════════════════════════════════════════════

def get_goals(status: str = None) -> list:
    if status:
        rows = execute_query(
            "SELECT * FROM goals WHERE status = %s ORDER BY time_bound NULLS LAST, title",
            (status,),
        )
    else:
        rows = execute_query("SELECT * FROM goals ORDER BY time_bound NULLS LAST, title")
    goals = [dict(r) for r in (rows or [])]
    for g in goals:
        g["progress_pct"] = goal_progress_pct(g)
        g["situation"] = goal_situation(g)
    return goals


def get_goal(goal_id: int):
    rows = execute_query("SELECT * FROM goals WHERE id = %s", (goal_id,))
    if not rows:
        return None
    g = dict(rows[0])
    g["progress_pct"] = goal_progress_pct(g)
    g["situation"] = goal_situation(g)
    return g


def upsert_goal(data: dict):
    goal_id = data.get("id")
    args = (
        data.get("title"),
        data.get("specific"),
        data.get("measurable"),
        data.get("achievable"),
        data.get("relevant"),
        data.get("time_bound") or None,
        _safe_float(data.get("target_value")),
        _safe_float(data.get("current_value")),
        data.get("unit") or "un.",
        data.get("status", "Em andamento"),
    )
    if goal_id:
        execute_query(
            """
            UPDATE goals SET title=%s, specific=%s, measurable=%s, achievable=%s,
                relevant=%s, time_bound=%s, target_value=%s, current_value=%s,
                unit=%s, status=%s, updated_at=NOW()
            WHERE id=%s
            """,
            args + (goal_id,),
            fetch=False,
        )
        return goal_id
    rows = execute_query(
        """
        INSERT INTO goals (title, specific, measurable, achievable, relevant,
            time_bound, target_value, current_value, unit, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """,
        args,
    )
    return rows[0]["id"] if rows else None


def delete_goal(goal_id: int):
    execute_query("DELETE FROM goals WHERE id=%s", (goal_id,), fetch=False)


# ══════════════════════════════════════════════════════════════════════════
# Histórico de avanço (check-ins)
# ══════════════════════════════════════════════════════════════════════════

def get_goal_progress_log(goal_id: int) -> list:
    rows = execute_query(
        "SELECT * FROM goal_progress_log WHERE goal_id=%s ORDER BY log_date ASC, id ASC",
        (goal_id,),
    )
    return [dict(r) for r in (rows or [])]


def add_goal_progress(goal_id: int, value: float, note: str = None, log_date=None):
    """Registra um check-in de avanço e atualiza goals.current_value para o
    valor mais recente informado (o card principal sempre reflete o último
    check-in)."""
    execute_query(
        """
        INSERT INTO goal_progress_log (goal_id, log_date, value, note)
        VALUES (%s, COALESCE(%s, CURRENT_DATE), %s, %s)
        """,
        (goal_id, log_date, _safe_float(value), note),
        fetch=False,
    )
    execute_query(
        "UPDATE goals SET current_value=%s, updated_at=NOW() WHERE id=%s",
        (_safe_float(value), goal_id),
        fetch=False,
    )


def delete_goal_progress(log_id: int):
    execute_query("DELETE FROM goal_progress_log WHERE id=%s", (log_id,), fetch=False)


# ══════════════════════════════════════════════════════════════════════════
# Plano de ação da meta (atividades/serviços vinculados via goal_id)
# ══════════════════════════════════════════════════════════════════════════

def get_goal_activities(goal_id: int) -> list:
    rows = execute_query(
        """
        SELECT * FROM activities
        WHERE goal_id = %s
        ORDER BY start_date NULLS LAST, end_date NULLS LAST, title
        """,
        (goal_id,),
    )
    activities = [dict(r) for r in (rows or [])]
    for a in activities:
        a["is_late"] = activity_is_late(a)
    return activities


def upsert_goal_activity(data: dict):
    """Cria/edita um 'serviço' do plano de ação (activities.goal_id = meta)."""
    activity_id = data.get("id")
    args = (
        data.get("title"),
        data.get("description") or None,
        data.get("start_date") or None,
        data.get("end_date") or None,
        data.get("status", "Não iniciado"),
        data.get("goal_id"),
    )
    if activity_id:
        execute_query(
            """
            UPDATE activities
            SET title=%s, description=%s, start_date=%s, end_date=%s, status=%s,
                goal_id=%s, updated_at=NOW()
            WHERE id=%s
            """,
            args + (activity_id,),
            fetch=False,
        )
        return activity_id
    rows = execute_query(
        """
        INSERT INTO activities (title, description, start_date, end_date, status, goal_id)
        VALUES (%s,%s,%s,%s,%s,%s) RETURNING id
        """,
        args,
    )
    return rows[0]["id"] if rows else None


def delete_goal_activity(activity_id: int):
    execute_query("DELETE FROM activities WHERE id=%s", (activity_id,), fetch=False)


# ══════════════════════════════════════════════════════════════════════════
# Plano de ação 5W2H de uma atividade (usado quando a atividade está atrasada)
# ══════════════════════════════════════════════════════════════════════════

def get_action_plans_for_activity(activity_id: int) -> list:
    rows = execute_query(
        "SELECT * FROM action_plan WHERE activity_id=%s ORDER BY when_date NULLS LAST, id",
        (activity_id,),
    )
    return [dict(r) for r in (rows or [])]


def upsert_action_plan(data: dict):
    plan_id = data.get("id")
    args = (
        data.get("activity_id"),
        data.get("what"),
        data.get("why"),
        data.get("who"),
        data.get("when_date") or None,
        data.get("where_place"),
        data.get("how"),
        _safe_float(data.get("how_much"), 0.0) or None,
        data.get("status", "Pendente"),
    )
    if plan_id:
        execute_query(
            """
            UPDATE action_plan SET activity_id=%s, what=%s, why=%s, who=%s,
                when_date=%s, where_place=%s, how=%s, how_much=%s, status=%s
            WHERE id=%s
            """,
            args + (plan_id,),
            fetch=False,
        )
        return plan_id
    rows = execute_query(
        """
        INSERT INTO action_plan (activity_id, what, why, who, when_date, where_place, how, how_much, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """,
        args,
    )
    return rows[0]["id"] if rows else None


def delete_action_plan(plan_id: int):
    execute_query("DELETE FROM action_plan WHERE id=%s", (plan_id,), fetch=False)


# ══════════════════════════════════════════════════════════════════════════
# Agregados para cards/resumo (usado também pela Home no futuro)
# ══════════════════════════════════════════════════════════════════════════

def get_goals_summary() -> dict:
    goals = get_goals()
    ativas = [g for g in goals if g["status"] == "Em andamento"]
    return {
        "total": len(goals),
        "ativas": len(ativas),
        "concluidas": len([g for g in goals if g["status"] == "Concluída"]),
        "atrasadas": len([g for g in ativas if g["situation"] == "atrasada"]),
        "media_progresso": round(sum(g["progress_pct"] for g in ativas) / len(ativas), 1) if ativas else 0.0,
    }
