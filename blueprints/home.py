"""
blueprints/home.py
Dashboard principal — KPIs do dia, fluxo de caixa, resumo do dia
(atividades/hábitos/treino), metas em andamento e orçado x realizado.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date

from flask import Blueprint, render_template, g

from database.queries import get_home_summary, get_cashflow_chart_data, get_budget_vs_actual
from database.queries_digest import get_today_activities
from database.queries_metas import get_goals

home_bp = Blueprint("home", __name__)


DAYS_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def _today_habits(user_id):
    try:
        from database.queries_habitos import get_today_habits, _is_scheduled
        today = date.today()
        df = get_today_habits(user_id)
        result = []
        if df is not None and not df.empty:
            for _, hr in df.iterrows():
                if _is_scheduled(today, hr.get("frequency_type", "Diário"), hr.get("frequency_days", "")):
                    result.append(hr.to_dict())
        return result
    except Exception:
        return None  # módulo não configurado ainda


def _today_workout(user_id):
    try:
        from database.queries_saude import get_divisions, get_exercises
        today_name = DAYS_PT[date.today().weekday()]
        df_divs = get_divisions(user_id)
        if df_divs is None or df_divs.empty:
            return None, [], today_name
        treino = None
        for _, div in df_divs.iterrows():
            if today_name in str(div.get("day_of_week") or ""):
                treino = div
                break
        if treino is None:
            free = df_divs[df_divs["day_of_week"].isna() | df_divs["day_of_week"].astype(str).str.contains("Livre", na=False)]
            if not free.empty:
                treino = free.iloc[0]
        if treino is None:
            return None, [], today_name
        exercises = get_exercises(user_id, int(treino["id"]))
        ex_list = exercises.to_dict("records") if exercises is not None and not exercises.empty else []
        return treino.to_dict(), ex_list, today_name
    except Exception:
        return None, [], DAYS_PT[date.today().weekday()]


@home_bp.route("/")
def index():
    user_id = g.user_id
    today = date.today()

    # As consultas abaixo são independentes entre si (tabelas/módulos
    # diferentes: finanças, atividades, hábitos, treino, metas, orçamento —
    # nenhuma depende do resultado de outra). Rodá-las em paralelo, cada uma
    # pegando sua própria conexão do pool (psycopg2 ThreadedConnectionPool é
    # thread-safe — ver database/connection.py), troca "soma das latências
    # de rede até o banco" por "a maior latência única": eram 8 round-trips
    # sequenciais até o Neon só pra montar a Home, o gargalo de performance
    # já documentado em connection.py. Se alguma levantar exceção, .result()
    # a repropaga aqui, igual ao comportamento sequencial anterior.
    with ThreadPoolExecutor(max_workers=7) as executor:
        f_summary = executor.submit(get_home_summary, user_id)
        f_cashflow = executor.submit(get_cashflow_chart_data, user_id, 6)
        f_activities = executor.submit(get_today_activities, user_id)
        f_habits = executor.submit(_today_habits, user_id)
        f_workout = executor.submit(_today_workout, user_id)
        f_goals = executor.submit(get_goals, user_id, "Em andamento")
        f_budget = executor.submit(get_budget_vs_actual, user_id, today.replace(day=1))

        summary = f_summary.result()
        df_cf = f_cashflow.result()
        activities_today = f_activities.result()
        habits_today = f_habits.result()
        workout, workout_exercises, workout_day = f_workout.result()
        active_goals = f_goals.result()
        df_bva = f_budget.result()

    cashflow = {"months": [], "income": [], "expense": [], "accumulated": []}
    if df_cf is not None and not df_cf.empty:
        for _, row in df_cf.iterrows():
            cashflow["months"].append(row["month"].strftime("%b/%y") if hasattr(row["month"], "strftime") else str(row["month"]))
            cashflow["income"].append(float(row["income"]))
            cashflow["expense"].append(float(row["expense"]))
            cashflow["accumulated"].append(float(row["accumulated"]))

    budget_rows = []
    if df_bva is not None and not df_bva.empty:
        for _, row in df_bva.iterrows():
            planned = float(row["planned"])
            actual = float(row["actual"])
            flow_type = row["flow_type"]
            if flow_type == "Entrada":
                diff = actual - planned
                ok = actual >= planned
            else:
                diff = planned - actual
                ok = actual <= planned
            budget_rows.append({
                "category": row["category"], "flow_type": flow_type,
                "planned": planned, "actual": actual, "diff": diff, "ok": ok,
            })
    budget_has_data = any(r["planned"] > 0 for r in budget_rows)

    return render_template(
        "home/index.html",
        summary=summary,
        cashflow=cashflow,
        activities_today=activities_today,
        habits_today=habits_today,
        workout=workout,
        workout_exercises=workout_exercises,
        workout_day=workout_day,
        active_goals=active_goals,
        budget_rows=budget_rows,
        budget_has_data=budget_has_data,
    )
