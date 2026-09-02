"""
database/queries_metas.py
Camada de acesso a dados do módulo Metas (SMART), independente de
database/queries.py. Reaproveita as tabelas `activities` e `action_plan` já
existentes: cada "serviço" do plano de ação de uma meta é uma linha em
`activities` com `goal_id` preenchido; o 5W2H de uma atividade atrasada
usa a tabela `action_plan` do jeito que já era usado por Atividades.

MULTIUSUÁRIO: toda função recebe `user_id` e filtra/estampa esse valor —
cada usuário só vê e só altera as próprias metas, check-ins e planos de ação.
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

def get_goals(user_id: int, status: str = None) -> list:
    if status:
        rows = execute_query(
            "SELECT * FROM goals WHERE user_id=%s AND status = %s ORDER BY time_bound NULLS LAST, title",
            (user_id, status),
        )
    else:
        rows = execute_query(
            "SELECT * FROM goals WHERE user_id=%s ORDER BY time_bound NULLS LAST, title",
            (user_id,),
        )
    goals = [dict(r) for r in (rows or [])]
    for g in goals:
        g["progress_pct"] = goal_progress_pct(g)
        g["situation"] = goal_situation(g)
    return goals


def get_goal(user_id: int, goal_id: int):
    rows = execute_query("SELECT * FROM goals WHERE id = %s AND user_id=%s", (goal_id, user_id))
    if not rows:
        return None
    g = dict(rows[0])
    g["progress_pct"] = goal_progress_pct(g)
    g["situation"] = goal_situation(g)
    return g


def upsert_goal(user_id: int, data: dict):
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
        rows = execute_query(
            """
            UPDATE goals SET title=%s, specific=%s, measurable=%s, achievable=%s,
                relevant=%s, time_bound=%s, target_value=%s, current_value=%s,
                unit=%s, status=%s, updated_at=NOW()
            WHERE id=%s AND user_id=%s
            RETURNING id
            """,
            args + (goal_id, user_id),
        )
        if not rows:
            raise PermissionError("Meta não encontrada.")
        return goal_id
    rows = execute_query(
        """
        INSERT INTO goals (title, specific, measurable, achievable, relevant,
            time_bound, target_value, current_value, unit, status, user_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """,
        args + (user_id,),
    )
    return rows[0]["id"] if rows else None


def delete_goal(user_id: int, goal_id: int):
    rows = execute_query(
        "DELETE FROM goals WHERE id=%s AND user_id=%s RETURNING id",
        (goal_id, user_id),
    )
    if not rows:
        raise PermissionError("Meta não encontrada.")


# ══════════════════════════════════════════════════════════════════════════
# Histórico de avanço (check-ins)
# ══════════════════════════════════════════════════════════════════════════

def get_goal_progress_log(user_id: int, goal_id: int) -> list:
    rows = execute_query(
        "SELECT * FROM goal_progress_log WHERE goal_id=%s AND user_id=%s ORDER BY log_date ASC, id ASC",
        (goal_id, user_id),
    )
    return [dict(r) for r in (rows or [])]


def add_goal_progress(user_id: int, goal_id: int, value: float, note: str = None, log_date=None):
    """Registra um check-in de avanço e atualiza goals.current_value para o
    valor mais recente informado (o card principal sempre reflete o último
    check-in)."""
    owner = execute_query("SELECT id FROM goals WHERE id=%s AND user_id=%s", (goal_id, user_id))
    if not owner:
        raise PermissionError("Meta não encontrada.")
    execute_query(
        """
        INSERT INTO goal_progress_log (goal_id, log_date, value, note, user_id)
        VALUES (%s, COALESCE(%s, CURRENT_DATE), %s, %s, %s)
        """,
        (goal_id, log_date, _safe_float(value), note, user_id),
        fetch=False,
    )
    execute_query(
        "UPDATE goals SET current_value=%s, updated_at=NOW() WHERE id=%s AND user_id=%s",
        (_safe_float(value), goal_id, user_id),
        fetch=False,
    )


def delete_goal_progress(user_id: int, log_id: int):
    rows = execute_query(
        "DELETE FROM goal_progress_log WHERE id=%s AND user_id=%s RETURNING id",
        (log_id, user_id),
    )
    if not rows:
        raise PermissionError("Registro não encontrado.")


# ══════════════════════════════════════════════════════════════════════════
# Plano de ação da meta (atividades/serviços vinculados via goal_id)
# ══════════════════════════════════════════════════════════════════════════

def get_goal_activities(user_id: int, goal_id: int) -> list:
    rows = execute_query(
        """
        SELECT * FROM activities
        WHERE goal_id = %s AND user_id = %s
        ORDER BY start_date NULLS LAST, end_date NULLS LAST, title
        """,
        (goal_id, user_id),
    )
    activities = [dict(r) for r in (rows or [])]
    for a in activities:
        a["is_late"] = activity_is_late(a)
    return activities


def upsert_goal_activity(user_id: int, data: dict):
    """Cria/edita um 'serviço' do plano de ação (activities.goal_id = meta)."""
    activity_id = data.get("id")
    goal_id = data.get("goal_id")
    if goal_id is not None:
        owner = execute_query("SELECT id FROM goals WHERE id=%s AND user_id=%s", (goal_id, user_id))
        if not owner:
            raise PermissionError("Meta não encontrada.")
    args = (
        data.get("title"),
        data.get("description") or None,
        data.get("start_date") or None,
        data.get("end_date") or None,
        data.get("status", "Não iniciado"),
        goal_id,
    )
    if activity_id:
        rows = execute_query(
            """
            UPDATE activities
            SET title=%s, description=%s, start_date=%s, end_date=%s, status=%s,
                goal_id=%s, updated_at=NOW()
            WHERE id=%s AND user_id=%s
            RETURNING id
            """,
            args + (activity_id, user_id),
        )
        if not rows:
            raise PermissionError("Atividade não encontrada.")
        return activity_id
    rows = execute_query(
        """
        INSERT INTO activities (title, description, start_date, end_date, status, goal_id, user_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """,
        args + (user_id,),
    )
    return rows[0]["id"] if rows else None


def delete_goal_activity(user_id: int, activity_id: int):
    rows = execute_query(
        "DELETE FROM activities WHERE id=%s AND user_id=%s RETURNING id",
        (activity_id, user_id),
    )
    if not rows:
        raise PermissionError("Atividade não encontrada.")


# Colunas que a tabela editável (estilo Excel) do plano de ação pode
# gravar direto por célula — allowlist fixa para nunca interpolar nome
# de coluna vindo do cliente sem checar.
ACTIVITY_EDITABLE_FIELDS = {"title", "description", "start_date", "end_date", "status"}


def update_activity_field(user_id: int, activity_id: int, field: str, value):
    """Salva uma célula editada da tabela de atividades (autosave)."""
    if field not in ACTIVITY_EDITABLE_FIELDS:
        raise ValueError(f"Campo não editável: {field}")
    if field in ("start_date", "end_date"):
        value = value or None
    else:
        value = (value or "").strip() or None
    rows = execute_query(
        f"UPDATE activities SET {field}=%s, updated_at=NOW() WHERE id=%s AND user_id=%s RETURNING id",
        (value, activity_id, user_id),
    )
    if not rows:
        raise PermissionError("Atividade não encontrada.")


# ══════════════════════════════════════════════════════════════════════════
# Plano de ação 5W2H de uma atividade (usado quando a atividade está atrasada)
# ══════════════════════════════════════════════════════════════════════════

def get_action_plans_for_activity(user_id: int, activity_id: int) -> list:
    rows = execute_query(
        "SELECT * FROM action_plan WHERE activity_id=%s AND user_id=%s ORDER BY when_date NULLS LAST, id",
        (activity_id, user_id),
    )
    return [dict(r) for r in (rows or [])]


def upsert_action_plan(user_id: int, data: dict):
    plan_id = data.get("id")
    activity_id = data.get("activity_id")
    if activity_id is not None:
        owner = execute_query("SELECT id FROM activities WHERE id=%s AND user_id=%s", (activity_id, user_id))
        if not owner:
            raise PermissionError("Atividade não encontrada.")
    args = (
        activity_id,
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
        rows = execute_query(
            """
            UPDATE action_plan SET activity_id=%s, what=%s, why=%s, who=%s,
                when_date=%s, where_place=%s, how=%s, how_much=%s, status=%s
            WHERE id=%s AND user_id=%s
            RETURNING id
            """,
            args + (plan_id, user_id),
        )
        if not rows:
            raise PermissionError("Item do plano de ação não encontrado.")
        return plan_id
    rows = execute_query(
        """
        INSERT INTO action_plan (activity_id, what, why, who, when_date, where_place, how, how_much, status, user_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """,
        args + (user_id,),
    )
    return rows[0]["id"] if rows else None


def delete_action_plan(user_id: int, plan_id: int):
    rows = execute_query(
        "DELETE FROM action_plan WHERE id=%s AND user_id=%s RETURNING id",
        (plan_id, user_id),
    )
    if not rows:
        raise PermissionError("Item do plano de ação não encontrado.")


ACTION_PLAN_EDITABLE_FIELDS = {"what", "why", "who", "when_date", "where_place", "how", "how_much", "status"}


def update_action_plan_field(user_id: int, plan_id: int, field: str, value):
    """Salva uma célula editada da tabela 5W2H (autosave)."""
    if field not in ACTION_PLAN_EDITABLE_FIELDS:
        raise ValueError(f"Campo não editável: {field}")
    if field == "how_much":
        value = _safe_float(value, 0.0) or None
    elif field == "when_date":
        value = value or None
    else:
        value = (value or "").strip() or None
    rows = execute_query(
        f"UPDATE action_plan SET {field}=%s WHERE id=%s AND user_id=%s RETURNING id",
        (value, plan_id, user_id),
    )
    if not rows:
        raise PermissionError("Item do plano de ação não encontrado.")


# ══════════════════════════════════════════════════════════════════════════
# Agregados para cards/resumo (usado também pela Home)
# ══════════════════════════════════════════════════════════════════════════

def get_goals_summary(user_id: int) -> dict:
    goals = get_goals(user_id)
    ativas = [g for g in goals if g["status"] == "Em andamento"]
    return {
        "total": len(goals),
        "ativas": len(ativas),
        "concluidas": len([g for g in goals if g["status"] == "Concluída"]),
        "atrasadas": len([g for g in ativas if g["situation"] == "atrasada"]),
        "media_progresso": round(sum(g["progress_pct"] for g in ativas) / len(ativas), 1) if ativas else 0.0,
    }
