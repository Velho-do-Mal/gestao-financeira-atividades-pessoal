"""
database/queries_saude.py
Queries do módulo Saúde — Musculação e Nutrição
"""

import streamlit as st
import pandas as pd
from datetime import date
from database.connection import execute_query, db_cursor


# ══════════════════════════════════════════════════════════════════════════════
# MUSCULAÇÃO — DIVISÕES
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=120, show_spinner=False)
def get_divisions() -> pd.DataFrame:
    rows = execute_query("""
        SELECT * FROM workout_divisions WHERE active=TRUE ORDER BY order_index, name
    """)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def upsert_division(data: dict):
    if data.get('id'):
        execute_query("""
            UPDATE workout_divisions SET name=%s, day_of_week=%s, muscle_groups=%s
            WHERE id=%s
        """, (data['name'], data.get('day_of_week'), data.get('muscle_groups'), data['id']),
             fetch=False)
    else:
        execute_query("""
            INSERT INTO workout_divisions (name, day_of_week, muscle_groups)
            VALUES (%s,%s,%s)
        """, (data['name'], data.get('day_of_week'), data.get('muscle_groups')), fetch=False)


def delete_division(div_id: int):
    execute_query("UPDATE workout_divisions SET active=FALSE WHERE id=%s", (div_id,), fetch=False)


# ══════════════════════════════════════════════════════════════════════════════
# MUSCULAÇÃO — EXERCÍCIOS
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=120, show_spinner=False)
def get_exercises(division_id: int) -> pd.DataFrame:
    rows = execute_query("""
        SELECT * FROM exercises WHERE division_id=%s AND active=TRUE ORDER BY order_index, name
    """, (division_id,))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


@st.cache_data(ttl=120, show_spinner=False)
def get_all_exercises() -> pd.DataFrame:
    rows = execute_query("""
        SELECT e.*, d.name AS division_name
        FROM exercises e JOIN workout_divisions d ON e.division_id=d.id
        WHERE e.active=TRUE ORDER BY d.order_index, e.order_index, e.name
    """)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def upsert_exercise(data: dict):
    if data.get('id'):
        execute_query("""
            UPDATE exercises SET name=%s, equipment=%s, notes=%s WHERE id=%s
        """, (data['name'], data.get('equipment'), data.get('notes'), data['id']), fetch=False)
    else:
        execute_query("""
            INSERT INTO exercises (division_id, name, equipment, notes, order_index)
            VALUES (%s,%s,%s,%s,%s)
        """, (data['division_id'], data['name'], data.get('equipment'),
               data.get('notes'), data.get('order_index', 0)), fetch=False)


def delete_exercise(ex_id: int):
    execute_query("UPDATE exercises SET active=FALSE WHERE id=%s", (ex_id,), fetch=False)


# ══════════════════════════════════════════════════════════════════════════════
# MUSCULAÇÃO — SÉRIES PLANEJADAS
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=120, show_spinner=False)
def get_exercise_sets(exercise_id: int) -> pd.DataFrame:
    rows = execute_query("""
        SELECT * FROM exercise_sets WHERE exercise_id=%s ORDER BY set_number
    """, (exercise_id,))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def upsert_exercise_set(data: dict):
    if data.get('id'):
        execute_query("""
            UPDATE exercise_sets SET set_number=%s, reps=%s, weight_kg=%s, notes=%s WHERE id=%s
        """, (data['set_number'], data.get('reps'), data.get('weight_kg'),
               data.get('notes'), data['id']), fetch=False)
    else:
        execute_query("""
            INSERT INTO exercise_sets (exercise_id, set_number, reps, weight_kg, notes)
            VALUES (%s,%s,%s,%s,%s)
        """, (data['exercise_id'], data['set_number'], data.get('reps'),
               data.get('weight_kg'), data.get('notes')), fetch=False)


def delete_exercise_set(set_id: int):
    execute_query("DELETE FROM exercise_sets WHERE id=%s", (set_id,), fetch=False)


# ══════════════════════════════════════════════════════════════════════════════
# MUSCULAÇÃO — LOG DE TREINO (HISTÓRICO)
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=60, show_spinner=False)
def get_workout_log(exercise_id: int, log_date: date = None) -> pd.DataFrame:
    if log_date:
        rows = execute_query("""
            SELECT * FROM workout_logs WHERE exercise_id=%s AND log_date=%s ORDER BY set_number
        """, (exercise_id, log_date))
    else:
        rows = execute_query("""
            SELECT * FROM workout_logs WHERE exercise_id=%s ORDER BY log_date DESC, set_number
            LIMIT 50
        """, (exercise_id,))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


@st.cache_data(ttl=60, show_spinner=False)
def get_weight_history(exercise_id: int) -> pd.DataFrame:
    """Histórico de carga máxima por dia para evolução."""
    rows = execute_query("""
        SELECT log_date, MAX(weight_done) AS max_weight, MAX(reps_done) AS max_reps
        FROM workout_logs WHERE exercise_id=%s
        GROUP BY log_date ORDER BY log_date DESC LIMIT 30
    """, (exercise_id,))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def save_workout_log(exercise_id: int, log_date: date, sets: list):
    """Salva log de treino — substitui registros do dia se existirem."""
    execute_query("DELETE FROM workout_logs WHERE exercise_id=%s AND log_date=%s",
                  (exercise_id, log_date), fetch=False)
    with db_cursor() as cur:
        for s in sets:
            cur.execute("""
                INSERT INTO workout_logs (exercise_id, set_number, reps_done, weight_done, log_date)
                VALUES (%s,%s,%s,%s,%s)
            """, (exercise_id, s['set_number'], s.get('reps_done'), s.get('weight_done'), log_date))


# ══════════════════════════════════════════════════════════════════════════════
# NUTRIÇÃO — ALIMENTOS
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300, show_spinner=False)
def get_foods(search: str = None) -> pd.DataFrame:
    if search:
        rows = execute_query("""
            SELECT * FROM foods WHERE active=TRUE AND name ILIKE %s
            ORDER BY name LIMIT 100
        """, (f'%{search}%',))
    else:
        rows = execute_query("SELECT * FROM foods WHERE active=TRUE ORDER BY name")
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def upsert_food(data: dict):
    if data.get('id'):
        execute_query("""
            UPDATE foods SET name=%s, preparation=%s, protein_g=%s, carbs_g=%s, fat_g=%s WHERE id=%s
        """, (data['name'], data.get('preparation'), data.get('protein_g', 0),
               data.get('carbs_g', 0), data.get('fat_g', 0), data['id']), fetch=False)
    else:
        execute_query("""
            INSERT INTO foods (name, preparation, protein_g, carbs_g, fat_g)
            VALUES (%s,%s,%s,%s,%s) ON CONFLICT (name) DO NOTHING
        """, (data['name'], data.get('preparation'), data.get('protein_g', 0),
               data.get('carbs_g', 0), data.get('fat_g', 0)), fetch=False)


def delete_food(food_id: int):
    execute_query("UPDATE foods SET active=FALSE WHERE id=%s", (food_id,), fetch=False)


# ══════════════════════════════════════════════════════════════════════════════
# NUTRIÇÃO — REFEIÇÕES
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=60, show_spinner=False)
def get_meals(meal_date: date) -> pd.DataFrame:
    rows = execute_query("""
        SELECT * FROM meals WHERE meal_date=%s ORDER BY meal_time NULLS LAST, name
    """, (meal_date,))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def upsert_meal(data: dict):
    if data.get('id'):
        execute_query("""
            UPDATE meals SET name=%s, meal_time=%s, notes=%s WHERE id=%s
        """, (data['name'], data.get('meal_time'), data.get('notes'), data['id']), fetch=False)
        return data['id']
    else:
        rows = execute_query("""
            INSERT INTO meals (name, meal_time, meal_date, notes)
            VALUES (%s,%s,%s,%s) RETURNING id
        """, (data['name'], data.get('meal_time'), data.get('meal_date', date.today()),
               data.get('notes')))
        return rows[0]['id'] if rows else None


def delete_meal(meal_id: int):
    execute_query("DELETE FROM meals WHERE id=%s", (meal_id,), fetch=False)


# ══════════════════════════════════════════════════════════════════════════════
# NUTRIÇÃO — ITENS DA REFEIÇÃO
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=60, show_spinner=False)
def get_meal_items(meal_id: int) -> pd.DataFrame:
    rows = execute_query("""
        SELECT mi.*, f.name AS food_name, f.preparation,
               f.protein_g, f.carbs_g, f.fat_g,
               ROUND(f.protein_g * mi.quantity_g / 100, 1) AS item_protein,
               ROUND(f.carbs_g   * mi.quantity_g / 100, 1) AS item_carbs,
               ROUND(f.fat_g     * mi.quantity_g / 100, 1) AS item_fat,
               ROUND((f.protein_g*4 + f.carbs_g*4 + f.fat_g*9) * mi.quantity_g / 100, 0) AS item_kcal
        FROM meal_items mi JOIN foods f ON mi.food_id=f.id
        WHERE mi.meal_id=%s ORDER BY mi.id
    """, (meal_id,))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def add_meal_item(meal_id: int, food_id: int, quantity_g: float):
    execute_query("""
        INSERT INTO meal_items (meal_id, food_id, quantity_g)
        VALUES (%s,%s,%s)
    """, (meal_id, food_id, quantity_g), fetch=False)


def delete_meal_item(item_id: int):
    execute_query("DELETE FROM meal_items WHERE id=%s", (item_id,), fetch=False)


# ══════════════════════════════════════════════════════════════════════════════
# NUTRIÇÃO — RESUMO DO DIA
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=60, show_spinner=False)
def get_daily_totals(meal_date: date) -> dict:
    rows = execute_query("""
        SELECT
            COALESCE(SUM(ROUND(f.protein_g * mi.quantity_g / 100, 1)), 0) AS total_protein,
            COALESCE(SUM(ROUND(f.carbs_g   * mi.quantity_g / 100, 1)), 0) AS total_carbs,
            COALESCE(SUM(ROUND(f.fat_g     * mi.quantity_g / 100, 1)), 0) AS total_fat,
            COALESCE(SUM(ROUND((f.protein_g*4 + f.carbs_g*4 + f.fat_g*9) * mi.quantity_g / 100, 0)), 0) AS total_kcal
        FROM meal_items mi
        JOIN foods f  ON mi.food_id  = f.id
        JOIN meals m  ON mi.meal_id  = m.id
        WHERE m.meal_date = %s
    """, (meal_date,))
    return dict(rows[0]) if rows else {'total_protein': 0, 'total_carbs': 0, 'total_fat': 0, 'total_kcal': 0}


# ══════════════════════════════════════════════════════════════════════════════
# NUTRIÇÃO — METAS DE MACROS
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300, show_spinner=False)
def get_macro_goals() -> dict:
    rows = execute_query("SELECT * FROM macro_goals ORDER BY id DESC LIMIT 1")
    if rows:
        return dict(rows[0])
    return {'protein_g': 150, 'carbs_g': 250, 'fat_g': 60, 'goal_kcal': 2000}


def save_macro_goals(protein_g: float, carbs_g: float, fat_g: float, goal_kcal: float):
    execute_query("DELETE FROM macro_goals", fetch=False)
    execute_query("""
        INSERT INTO macro_goals (protein_g, carbs_g, fat_g, goal_kcal)
        VALUES (%s,%s,%s,%s)
    """, (protein_g, carbs_g, fat_g, goal_kcal), fetch=False)


# ══════════════════════════════════════════════════════════════════════════════
# SEED — BASE DE ALIMENTOS PRÉ-CARREGADA
# ══════════════════════════════════════════════════════════════════════════════

FOODS_SEED = [
    # (nome, preparo, proteina, carbo, gordura) — valores por 100g
    # ─── CARNES E PROTEÍNAS ─────────────────────────────────────────
    ("Frango peito", "Cozido",    31.0,  0.0,  3.6),
    ("Frango peito", "Grelhado",  32.0,  0.0,  3.2),
    ("Frango peito", "Assado",    30.0,  0.0,  4.0),
    ("Frango peito", "Frito",     28.0,  4.0, 10.0),
    ("Frango coxa",  "Cozido",    26.0,  0.0,  9.0),
    ("Frango coxa",  "Grelhado",  27.0,  0.0,  8.5),
    ("Frango coxa",  "Assado",    25.0,  0.0, 10.0),
    ("Frango filé",  "Grelhado",  31.0,  0.0,  3.0),
    ("Frango à milanesa", "Frito",22.0, 12.0, 14.0),
    ("Carne bovina patinho", "Cozido",  28.0,  0.0,  6.0),
    ("Carne bovina alcatra", "Grelhado",27.0,  0.0,  8.0),
    ("Carne bovina filé mignon", "Grelhado", 29.0, 0.0, 6.0),
    ("Carne bovina picanha", "Grelhado", 25.0, 0.0, 18.0),
    ("Carne bovina acém", "Cozido", 26.0, 0.0, 10.0),
    ("Carne moída", "Cozido",     24.0,  0.0, 12.0),
    ("Carne moída", "Grelhado",   26.0,  0.0, 10.0),
    ("Carne bovina", "Frito",     24.0,  0.0, 20.0),
    ("Carne suína lombo", "Grelhado", 27.0, 0.0, 8.0),
    ("Carne suína lombo", "Assado",   26.0, 0.0, 9.0),
    ("Costela suína", "Assado",   21.0,  0.0, 22.0),
    ("Tilápia", "Grelhado",       26.0,  0.0,  3.0),
    ("Tilápia", "Assado",         25.0,  0.0,  3.5),
    ("Salmão", "Grelhado",        25.0,  0.0, 13.0),
    ("Salmão", "Assado",          24.0,  0.0, 14.0),
    ("Atum", "Cozido",            30.0,  0.0,  1.0),
    ("Sardinha", "Assado",        21.0,  0.0, 11.0),
    ("Camarão", "Cozido",         24.0,  0.0,  1.2),
    ("Camarão", "Grelhado",       23.0,  0.0,  1.5),
    ("Ovo inteiro", "Cozido",     13.0,  1.1, 11.0),
    ("Ovo inteiro", "Mexido",     10.0,  2.0, 12.0),
    ("Ovo inteiro", "Frito",      11.0,  0.5, 15.0),
    ("Ovo inteiro", "Grelhado",   12.0,  1.0, 10.5),
    ("Clara de ovo", "Cozido",    11.0,  0.7,  0.2),
    # ─── CARBOIDRATOS ───────────────────────────────────────────────
    ("Arroz branco",   "Cozido",   2.5, 28.0,  0.2),
    ("Arroz integral", "Cozido",   2.6, 23.0,  1.0),
    ("Feijão preto",   "Cozido",   7.0, 14.0,  0.5),
    ("Feijão carioca", "Cozido",   8.0, 14.0,  0.5),
    ("Feijão branco",  "Cozido",   7.5, 16.0,  0.5),
    ("Lentilha",       "Cozido",   9.0, 20.0,  0.4),
    ("Grão-de-bico",   "Cozido",   9.0, 27.0,  3.0),
    ("Ervilha",        "Cozido",   5.0, 14.0,  0.4),
    ("Batata inglesa", "Cozido",   2.0, 17.0,  0.1),
    ("Batata inglesa", "Assado",   2.5, 20.0,  0.1),
    ("Batata frita",   "Frito",    3.5, 35.0, 15.0),
    ("Batata doce",    "Cozido",   1.4, 20.0,  0.1),
    ("Batata doce",    "Assado",   2.0, 21.0,  0.1),
    ("Mandioca",       "Cozido",   1.0, 30.0,  0.3),
    ("Mandioquinha",   "Cozido",   1.0, 16.0,  0.2),
    ("Macarrão",       "Cozido",   5.0, 25.0,  0.9),
    ("Macarrão integral", "Cozido",7.0, 22.0,  1.5),
    ("Quinoa",         "Cozido",   4.0, 21.0,  2.0),
    ("Milho",          "Cozido",   3.0, 19.0,  1.2),
    ("Pão integral",   "Assado",   9.0, 42.0,  5.0),
    ("Tapioca",        "Assado",   0.6, 25.0,  0.1),
    ("Aveia em flocos","Cozido",   5.0, 15.0,  2.5),
    # ─── VEGETAIS ───────────────────────────────────────────────────
    ("Brócolis",       "Cozido",   2.8,  5.0,  0.4),
    ("Couve-flor",     "Cozido",   1.9,  4.0,  0.3),
    ("Espinafre",      "Cozido",   3.0,  3.5,  0.5),
    ("Abobrinha",      "Cozido",   1.0,  3.0,  0.3),
    ("Abobrinha",      "Grelhado", 1.2,  3.0,  2.0),
    ("Cenoura",        "Cozido",   0.8,  8.0,  0.2),
    ("Beterraba",      "Cozido",   1.7,  9.0,  0.2),
    ("Couve",          "Cozido",   2.0,  4.0,  1.0),
    ("Repolho",        "Cozido",   1.0,  3.5,  0.1),
    ("Chuchu",         "Cozido",   0.7,  4.0,  0.1),
    ("Berinjela",      "Assado",   1.0,  6.0,  0.3),
    ("Pimentão",       "Assado",   1.0,  7.0,  0.5),
    ("Tomate",         "Assado",   1.0,  5.0,  0.4),
    # ─── LATICÍNIOS ─────────────────────────────────────────────────
    ("Iogurte grego natural", "Cru", 10.0, 4.0,  5.0),
    ("Queijo cottage",        "Cru", 11.0, 3.0,  4.0),
    ("Ricota",                "Cru",  8.0, 3.0,  4.5),
    ("Leite desnatado",       "Cru",  3.4, 5.0,  0.1),
    ("Leite integral",        "Cru",  3.2, 5.0,  3.5),
    ("Queijo minas frescal",  "Cru", 17.0, 2.0, 10.0),
    # ─── FRUTAS CRUAS ───────────────────────────────────────────────
    ("Banana prata",   "Cru",  1.3, 23.0,  0.3),
    ("Banana maçã",    "Cru",  1.4, 21.0,  0.3),
    ("Maçã",           "Cru",  0.3, 14.0,  0.2),
    ("Laranja",        "Cru",  1.0, 12.0,  0.2),
    ("Laranja lima",   "Cru",  0.8, 11.0,  0.2),
    ("Manga",          "Cru",  0.5, 15.0,  0.3),
    ("Uva",            "Cru",  0.7, 17.0,  0.4),
    ("Morango",        "Cru",  0.7,  8.0,  0.3),
    ("Melão",          "Cru",  0.5,  8.0,  0.2),
    ("Abacaxi",        "Cru",  0.5, 12.0,  0.1),
    ("Mamão papaia",   "Cru",  0.5, 10.0,  0.1),
    ("Kiwi",           "Cru",  1.0, 15.0,  0.5),
    ("Pêra",           "Cru",  0.4, 15.0,  0.1),
    ("Pêssego",        "Cru",  0.9, 10.0,  0.3),
    ("Melancia",       "Cru",  0.6,  8.0,  0.2),
    ("Abacate",        "Cru",  2.0,  9.0, 15.0),
    ("Coco fresco",    "Cru",  4.0, 10.0, 37.0),
    ("Maracujá polpa", "Cru",  2.4, 13.0,  0.7),
    ("Goiaba",         "Cru",  2.6, 14.0,  1.0),
    ("Framboesa",      "Cru",  1.2, 12.0,  0.7),
    ("Mirtilo",        "Cru",  0.7, 14.0,  0.3),
    ("Cereja",         "Cru",  1.0, 16.0,  0.3),
    ("Ameixa",         "Cru",  0.7, 11.0,  0.3),
    ("Tangerina",      "Cru",  0.8, 13.0,  0.3),
    ("Limão",          "Cru",  1.1,  7.0,  0.3),
    # ─── OUTROS ─────────────────────────────────────────────────────
    ("Whey protein",   "Cru",  80.0,  6.0,  4.0),
    ("Amendoim",       "Assado", 26.0, 20.0, 46.0),
    ("Castanha de caju","Assado", 18.0, 30.0, 46.0),
    ("Azeite de oliva","Cru",     0.0,  0.0,100.0),
    ("Mel",            "Cru",     0.3, 82.0,  0.0),
    ("Pasta de amendoim","Cru",  25.0, 20.0, 50.0),
]


def seed_foods_if_empty():
    """Popula base de alimentos na primeira execução."""
    rows = execute_query("SELECT COUNT(*) AS n FROM foods WHERE active=TRUE")
    if rows and int(rows[0]['n']) > 0:
        return  # Já tem dados, não repopula
    with db_cursor() as cur:
        for name, prep, prot, carbs, fat in FOODS_SEED:
            full_name = f"{name} {prep.lower()}" if prep not in ('Cru',) else name
            cur.execute("""
                INSERT INTO foods (name, preparation, protein_g, carbs_g, fat_g)
                VALUES (%s,%s,%s,%s,%s) ON CONFLICT (name) DO NOTHING
            """, (full_name, prep, prot, carbs, fat))
