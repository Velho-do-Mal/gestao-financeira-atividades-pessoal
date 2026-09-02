"""
database/queries.py
Camada de acesso a dados — todas as queries SQL do sistema BK Finance

CORREÇÕES v2:
  - @st.cache_data(ttl=120) nas funções de leitura → elimina re-queries desnecessárias
  - INTERVAL '%s months' substituído por aritmética de data Python → sem ambiguidade de tipo
  - update_transaction: seta is_forecast=False quando status='Pago' (corrige inconsistência)
  - Adicionadas: get_all_subcategories(), delete_recurrence_group(), get_all_bank_balances()
  - current_balance calculado dinamicamente (não depende mais da coluna desatualizada)
"""

import pandas as pd
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from database.connection import execute_query, db_cursor
from typing import Optional
import uuid


# ══════════════════════════════════════════════════════════════════════════════
# CACHE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def clear_data_cache():
    """
    Mantido por compatibilidade — na migração para Flask não há mais cache
    de leitura em memória (cada request consulta o Postgres diretamente),
    então esta função é um no-op.
    """
    pass


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD / HOME
# ══════════════════════════════════════════════════════════════════════════════

def get_home_summary() -> dict:
    """Retorna indicadores para o painel Home."""
    rows = execute_query("""
        SELECT
            COALESCE(SUM(CASE WHEN flow_type='Saída'  AND status='Não pago' AND due_date < CURRENT_DATE  THEN total_value END), 0) AS overdue,
            COALESCE(SUM(CASE WHEN flow_type='Saída'  AND status='Não pago' AND due_date BETWEEN CURRENT_DATE AND CURRENT_DATE+3 THEN total_value END), 0) AS due_soon,
            COALESCE(SUM(CASE WHEN flow_type='Entrada' AND status='Não pago' THEN total_value END), 0) AS receivable,
            COALESCE(SUM(CASE WHEN flow_type='Entrada' AND status='Pago'    AND payment_date = CURRENT_DATE THEN total_value END), 0) AS income_today,
            COALESCE(SUM(CASE WHEN flow_type='Saída'  AND status='Pago'    AND payment_date = CURRENT_DATE THEN total_value END), 0) AS expense_today
        FROM transactions
    """)
    r = dict(rows[0]) if rows else {}
    r['balance_today'] = r.get('income_today', 0) - r.get('expense_today', 0)
    return r


def get_cashflow_chart_data(months: int = 6) -> pd.DataFrame:
    """Dados do gráfico de barras + linha para os últimos N meses.
    CORREÇÃO: usa aritmética de data Python em vez de INTERVAL '%s months'.
    """
    start = date.today().replace(day=1) - relativedelta(months=months)
    rows = execute_query("""
        SELECT
            DATE_TRUNC('month', due_date)::date AS month,
            SUM(CASE WHEN flow_type='Entrada' AND status='Pago' THEN total_value ELSE 0 END) AS income,
            SUM(CASE WHEN flow_type='Saída'  AND status='Pago' THEN total_value ELSE 0 END) AS expense
        FROM transactions
        WHERE due_date >= %s
        GROUP BY 1
        ORDER BY 1
    """, (start,))
    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=['month', 'income', 'expense'])
    if not df.empty:
        df['balance']     = df['income'] - df['expense']
        df['accumulated'] = df['balance'].cumsum()
    return df


def get_today_activities() -> pd.DataFrame:
    """Atividades que vencem hoje, ordenadas por prioridade."""
    rows = execute_query("""
        SELECT id, title, priority, status, end_date, parent_id
        FROM activities
        WHERE end_date = CURRENT_DATE AND status != 'Concluído'
        ORDER BY
            CASE priority
                WHEN 'Urgente-Urgente'           THEN 1
                WHEN 'Importante-Urgente'        THEN 2
                WHEN 'Importante não Urgente'    THEN 3
                WHEN 'Não importante-Não urgente' THEN 4
            END,
            title
    """)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# FORNECEDORES
# ══════════════════════════════════════════════════════════════════════════════

def get_suppliers() -> pd.DataFrame:
    rows = execute_query("SELECT * FROM suppliers WHERE active=TRUE ORDER BY name")
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def upsert_supplier(data: dict):
    if data.get('id'):
        execute_query("""
            UPDATE suppliers SET name=%s, document=%s, email=%s, phone=%s,
            address=%s, notes=%s, updated_at=NOW() WHERE id=%s
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


SUPPLIER_EDITABLE_FIELDS = {"name", "document", "email", "phone", "address", "notes"}


def update_supplier_field(supplier_id: int, field: str, value):
    if field not in SUPPLIER_EDITABLE_FIELDS:
        raise ValueError(f"Campo não editável: {field}")
    value = (value or "").strip() or None
    execute_query(
        f"UPDATE suppliers SET {field}=%s, updated_at=NOW() WHERE id=%s",
        (value, supplier_id), fetch=False,
    )


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORIAS / SUBCATEGORIAS
# ══════════════════════════════════════════════════════════════════════════════

def get_categories(flow_type: Optional[str] = None) -> pd.DataFrame:
    if flow_type and flow_type != 'Todos':
        rows = execute_query("""
            SELECT * FROM categories WHERE active=TRUE
            AND (flow_type=%s OR flow_type='Ambos') ORDER BY name
        """, (flow_type,))
    else:
        rows = execute_query("SELECT * FROM categories WHERE active=TRUE ORDER BY flow_type, name")
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def get_subcategories(category_id: int) -> pd.DataFrame:
    rows = execute_query("""
        SELECT * FROM subcategories WHERE category_id=%s AND active=TRUE ORDER BY name
    """, (category_id,))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def get_all_subcategories() -> pd.DataFrame:
    """
    Retorna TODAS as subcategorias ativas de uma vez.
    Usar no lugar de get_subcategories() dentro de loops para evitar N queries.
    """
    rows = execute_query("""
        SELECT * FROM subcategories WHERE active=TRUE ORDER BY category_id, name
    """)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def upsert_category(flow_type: str, name: str, cat_id: int = None):
    if cat_id:
        execute_query("UPDATE categories SET flow_type=%s, name=%s WHERE id=%s",
                      (flow_type, name, cat_id), fetch=False)
    else:
        execute_query("""
            INSERT INTO categories (flow_type, name) VALUES (%s,%s)
            ON CONFLICT (flow_type, name) DO UPDATE SET flow_type=EXCLUDED.flow_type
        """, (flow_type, name), fetch=False)


def upsert_subcategory(category_id: int, name: str, sub_id: int = None):
    if sub_id:
        execute_query("UPDATE subcategories SET name=%s WHERE id=%s", (name, sub_id), fetch=False)
    else:
        execute_query("""
            INSERT INTO subcategories (category_id, name) VALUES (%s,%s)
            ON CONFLICT (category_id, name) DO UPDATE SET name=EXCLUDED.name
        """, (category_id, name), fetch=False)


def delete_category(cat_id: int):
    execute_query("UPDATE categories SET active=FALSE WHERE id=%s", (cat_id,), fetch=False)


def delete_subcategory(sub_id: int):
    execute_query("UPDATE subcategories SET active=FALSE WHERE id=%s", (sub_id,), fetch=False)


def update_category_field(cat_id: int, field: str, value):
    if field not in {"name", "flow_type"}:
        raise ValueError(f"Campo não editável: {field}")
    value = (value or "").strip()
    if not value:
        raise ValueError("Nome não pode ficar em branco")
    execute_query(f"UPDATE categories SET {field}=%s WHERE id=%s", (value, cat_id), fetch=False)


def update_subcategory_field(sub_id: int, field: str, value):
    if field != "name":
        raise ValueError(f"Campo não editável: {field}")
    value = (value or "").strip()
    if not value:
        raise ValueError("Nome não pode ficar em branco")
    execute_query("UPDATE subcategories SET name=%s WHERE id=%s", (value, sub_id), fetch=False)


# ══════════════════════════════════════════════════════════════════════════════
# BANCOS
# ══════════════════════════════════════════════════════════════════════════════

def get_banks() -> pd.DataFrame:
    rows = execute_query("SELECT * FROM banks WHERE active=TRUE ORDER BY name")
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def get_all_bank_balances() -> pd.DataFrame:
    """
    Saldo atual calculado dinamicamente: saldo_inicial + entradas_pagas - saídas_pagas.
    CORREÇÃO: a coluna current_balance no banco nunca era atualizada; aqui calculamos na query.
    """
    rows = execute_query("""
        SELECT
            b.id, b.name, b.account, b.agency,
            b.initial_balance,
            b.initial_balance
                + COALESCE(SUM(CASE WHEN t.flow_type='Entrada' AND t.status='Pago' THEN t.total_value ELSE 0 END), 0)
                - COALESCE(SUM(CASE WHEN t.flow_type='Saída'   AND t.status='Pago' THEN t.total_value ELSE 0 END), 0)
            AS current_balance
        FROM banks b
        LEFT JOIN transactions t ON t.bank_id = b.id
        WHERE b.active = TRUE
        GROUP BY b.id, b.name, b.account, b.agency, b.initial_balance
        ORDER BY b.name
    """)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def get_total_initial_balance() -> float:
    rows = execute_query("SELECT COALESCE(SUM(initial_balance),0) AS total FROM banks WHERE active=TRUE")
    return float(rows[0]['total']) if rows else 0.0


def upsert_bank(data: dict):
    if data.get('id'):
        execute_query("""
            UPDATE banks SET name=%s, account=%s, agency=%s, initial_balance=%s WHERE id=%s
        """, (data['name'], data.get('account'), data.get('agency'),
               data.get('initial_balance', 0), data['id']), fetch=False)
    else:
        execute_query("""
            INSERT INTO banks (name, account, agency, initial_balance, current_balance)
            VALUES (%s,%s,%s,%s,%s)
        """, (data['name'], data.get('account'), data.get('agency'),
               data.get('initial_balance', 0), data.get('initial_balance', 0)), fetch=False)


def delete_bank(bank_id: int):
    execute_query("UPDATE banks SET active=FALSE WHERE id=%s", (bank_id,), fetch=False)


BANK_EDITABLE_FIELDS = {"name", "account", "agency", "initial_balance"}


def update_bank_field(bank_id: int, field: str, value):
    if field not in BANK_EDITABLE_FIELDS:
        raise ValueError(f"Campo não editável: {field}")
    if field == "initial_balance":
        value = _safe_float(value, 0.0)
    else:
        value = (value or "").strip() or None
    execute_query(f"UPDATE banks SET {field}=%s WHERE id=%s", (value, bank_id), fetch=False)


# ══════════════════════════════════════════════════════════════════════════════
# MOVIMENTAÇÕES
# ══════════════════════════════════════════════════════════════════════════════

def get_transactions(
    start_date=None, end_date=None,
    status=None, flow_type=None, is_forecast=None,
) -> pd.DataFrame:
    """
    Retorna transações com joins de categoria, subcategoria, fornecedor e banco.
    PERFORMANCE: resultado cacheado por 2 minutos. Chame clear_data_cache() após writes.
    """
    conditions = ["1=1"]
    params = []
    if start_date:
        conditions.append("t.due_date >= %s"); params.append(start_date)
    if end_date:
        conditions.append("t.due_date <= %s"); params.append(end_date)
    if status and status != 'Todos':
        conditions.append("t.status = %s"); params.append(status)
    if flow_type and flow_type != 'Todos':
        conditions.append("t.flow_type = %s"); params.append(flow_type)
    if is_forecast is not None:
        conditions.append("t.is_forecast = %s"); params.append(is_forecast)

    where = " AND ".join(conditions)
    rows = execute_query(f"""
        SELECT
            t.id, t.flow_type, t.category_id, t.subcategory_id,
            t.supplier_id, t.bank_id, t.description,
            t.value, t.interest, t.total_value,
            t.due_date, t.payment_date, t.status,
            t.is_recurrent, t.recurrence_type, t.recurrence_group_id,
            t.notes, t.is_forecast, t.created_at, t.updated_at,
            c.name  AS category_name,
            s.name  AS subcategory_name,
            sup.name AS supplier_name,
            b.name  AS bank_name
        FROM transactions t
        LEFT JOIN categories  c   ON t.category_id    = c.id
        LEFT JOIN subcategories s ON t.subcategory_id  = s.id
        LEFT JOIN suppliers   sup ON t.supplier_id     = sup.id
        LEFT JOIN banks       b   ON t.bank_id         = b.id
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
            if rec_type == 'Mensal':
                next_due = base_due + relativedelta(months=i)
            elif rec_type == 'Diário':
                next_due = base_due + timedelta(days=i)
            elif rec_type == 'Anual':
                next_due = base_due + relativedelta(years=i)
            else:
                next_due = base_due + relativedelta(months=i)
            records.append((data.copy(), next_due))

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
                rec_data.get('is_forecast', True),
            ))


def _safe_date(v):
    """Converte valor para date ou None — trata NaT, string vazia, None."""
    if v is None: return None
    try:
        import pandas as _pd
        if _pd.isnull(v): return None
    except Exception: pass
    if str(v).strip() in ('', 'None', 'NaT', 'nat'): return None
    return v


def update_transaction(transaction_id: int, data: dict):
    """
    Atualiza movimentação.
    FIX: suporta bank_id + datas seguras (None/NaT nunca chegam ao banco como string).
    """
    is_forecast = False if data.get('status') == 'Pago' else data.get('is_forecast', True)
    execute_query("""
        UPDATE transactions
        SET flow_type=%s, category_id=%s, subcategory_id=%s, bank_id=%s,
            value=%s, interest=%s, due_date=%s, status=%s, payment_date=%s,
            description=%s, is_forecast=%s, updated_at=NOW()
        WHERE id=%s
    """, (
        data['flow_type'], data.get('category_id'), data.get('subcategory_id'),
        data.get('bank_id'),
        data.get('value', 0), data.get('interest', 0),
        _safe_date(data.get('due_date')),
        data.get('status', 'Não pago'),
        _safe_date(data.get('payment_date')),
        data.get('description'), is_forecast, transaction_id,
    ), fetch=False)


def delete_transaction(transaction_id: int):
    execute_query("DELETE FROM transactions WHERE id=%s", (transaction_id,), fetch=False)


def _safe_float(val, default=0.0):
    try:
        if val is None or val == "":
            return default
        return float(str(val).replace(",", "."))
    except (TypeError, ValueError):
        return default


# Colunas que a tabela de Lançamentos edita direto por célula (autosave).
TRANSACTION_EDITABLE_FIELDS = {
    "description", "value", "interest", "due_date", "payment_date",
    "status", "category_id", "subcategory_id", "bank_id", "supplier_id",
}


def update_transaction_field(transaction_id: int, field: str, value):
    """Salva uma célula editada da tabela de Lançamentos (autosave).
    Ao editar 'status', mantém is_forecast coerente (Pago => False),
    igual já fazia update_transaction()."""
    if field not in TRANSACTION_EDITABLE_FIELDS:
        raise ValueError(f"Campo não editável: {field}")

    if field in ("category_id", "subcategory_id", "bank_id", "supplier_id"):
        value = int(value) if value not in (None, "") else None
    elif field in ("value", "interest"):
        value = _safe_float(value, 0.0) if value not in (None, "") else 0.0
    elif field in ("due_date", "payment_date"):
        value = _safe_date(value)
    else:
        value = (value or "").strip() or None

    if field == "status":
        is_forecast = False if value == "Pago" else True
        execute_query(
            "UPDATE transactions SET status=%s, is_forecast=%s, updated_at=NOW() WHERE id=%s",
            (value, is_forecast, transaction_id), fetch=False,
        )
        return

    execute_query(
        f"UPDATE transactions SET {field}=%s, updated_at=NOW() WHERE id=%s",
        (value, transaction_id), fetch=False,
    )


def delete_recurrence_group(group_id: str):
    """
    Exclui TODAS as transações pertencentes a um grupo de recorrência.
    Novo em v2 — permite exclusão em lote pelo grupo.
    """
    execute_query(
        "DELETE FROM transactions WHERE recurrence_group_id::text = %s",
        (str(group_id),), fetch=False,
    )


def get_cashflow_planned_vs_actual(months: int = 24) -> pd.DataFrame:
    """
    Retorna dados de previsto x realizado por mês.
    CORREÇÃO: usa aritmética Python em vez de INTERVAL '%s months'.
    """
    start = date.today().replace(day=1) - relativedelta(months=1)
    end   = date.today().replace(day=1) + relativedelta(months=months)
    rows = execute_query("""
        SELECT
            DATE_TRUNC('month', due_date)::date AS month,
            flow_type,
            is_forecast,
            SUM(total_value) AS total
        FROM transactions
        WHERE due_date >= %s AND due_date < %s
        GROUP BY 1, 2, 3
        ORDER BY 1, 2
    """, (start, end))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def build_cashflow_pivot(is_forecast: bool, months: int = 12) -> tuple:
    """
    Tabela pivô de fluxo de caixa (categoria/subcategoria x mês), usada nas
    abas Previsto/Realizado/Diferença de Finanças → Movimentações.
    Busca tudo de uma vez e agrega em pandas (3 queries no total, não uma
    por célula da tabela).
    """
    today = date.today().replace(day=1)
    month_dates = [today + relativedelta(months=i) for i in range(months)]
    month_labels = [m.strftime("%b/%Y") for m in month_dates]

    period_start = month_dates[0]
    period_end = month_dates[-1] + relativedelta(months=1) - relativedelta(days=1)

    df_cats = get_categories()
    df_subs = get_all_subcategories()
    df_all = get_transactions(start_date=period_start, end_date=period_end, is_forecast=is_forecast)

    if df_cats.empty:
        return pd.DataFrame(), month_labels

    if not df_all.empty:
        df_all = df_all.copy()
        df_all["month_str"] = pd.to_datetime(df_all["due_date"]).dt.strftime("%b/%Y")
        df_all["category_id"] = pd.to_numeric(df_all["category_id"], errors="coerce")
        df_all["subcategory_id"] = pd.to_numeric(df_all["subcategory_id"], errors="coerce")
        df_all["total_value"] = pd.to_numeric(df_all["total_value"], errors="coerce").fillna(0)

    rows = []
    for _, cat in df_cats.iterrows():
        cat_id = int(cat["id"])
        cat_subs = df_subs[df_subs["category_id"] == cat_id] if not df_subs.empty else pd.DataFrame()
        # Sempre inclui o bucket "sem subcategoria" além de cada subcategoria
        # cadastrada — uma categoria com subcategorias ainda pode ter
        # lançamentos sem subcategoria escolhida, e eles não podem "sumir"
        # da tabela (bug corrigido em relação à versão Streamlit original).
        entries = [(None, "—")] + ([] if cat_subs.empty else [(int(s["id"]), s["name"]) for _, s in cat_subs.iterrows()])

        for sub_id, sub_name in entries:
            row = {"flow_type": cat["flow_type"], "category": cat["name"], "subcategory": sub_name}
            if df_all.empty:
                for ml in month_labels:
                    row[ml] = 0.0
            else:
                df_cat = df_all[df_all["category_id"] == cat_id]
                df_sub_data = df_cat[df_cat["subcategory_id"] == sub_id] if sub_id is not None else df_cat[df_cat["subcategory_id"].isna()]
                if not df_sub_data.empty:
                    agg = df_sub_data.groupby("month_str")["total_value"].sum()
                    for ml in month_labels:
                        row[ml] = float(agg.get(ml, 0.0))
                else:
                    for ml in month_labels:
                        row[ml] = 0.0
            rows.append(row)

    return pd.DataFrame(rows), month_labels


# ══════════════════════════════════════════════════════════════════════════════
# METAS
# ══════════════════════════════════════════════════════════════════════════════

def get_goals() -> pd.DataFrame:
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


# ══════════════════════════════════════════════════════════════════════════════
# ORÇAMENTO
# ══════════════════════════════════════════════════════════════════════════════

def get_budget(year_month: date) -> pd.DataFrame:
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
    """
    Upsert de orçamento usando os índices parciais NULL-safe (corrigido v2).
    Para sub=NULL usa ON CONFLICT DO UPDATE pelo índice uniq_budget_no_sub.
    """
    if subcategory_id is None:
        execute_query("""
            INSERT INTO budget (category_id, subcategory_id, year_month, planned_value)
            VALUES (%s, NULL, %s, %s)
            ON CONFLICT ON CONSTRAINT budget_pkey DO NOTHING
        """, (category_id, year_month, planned_value), fetch=False)
        # Atualiza se já existir (índice parcial não suporta ON CONFLICT direto no INSERT)
        execute_query("""
            UPDATE budget SET planned_value=%s, updated_at=NOW()
            WHERE category_id=%s AND subcategory_id IS NULL AND year_month=%s
        """, (planned_value, category_id, year_month), fetch=False)
    else:
        execute_query("""
            INSERT INTO budget (category_id, subcategory_id, year_month, planned_value)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT (category_id, subcategory_id, year_month)
            DO UPDATE SET planned_value=%s, updated_at=NOW()
        """, (category_id, subcategory_id, year_month, planned_value, planned_value), fetch=False)


def get_budget_vs_actual(year_month: date) -> pd.DataFrame:
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


# ══════════════════════════════════════════════════════════════════════════════
# ATIVIDADES
# ══════════════════════════════════════════════════════════════════════════════

def get_activities(only_standalone: bool = False) -> pd.DataFrame:
    """Lista atividades. Com only_standalone=True, exclui as vinculadas a uma
    meta (goal_id preenchido) — essas são geridas dentro do módulo Metas."""
    where = "WHERE goal_id IS NULL" if only_standalone else ""
    rows = execute_query(f"""
        SELECT * FROM activities
        {where}
        ORDER BY COALESCE(parent_id, id), parent_id NULLS FIRST, order_index, title
    """)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _safe_int(val):
    """Converte para int Python ou None (lida com numpy int64 / NaN)."""
    try:
        if val is None: return None
        if pd.isna(val): return None
        return int(val)
    except Exception:
        return None


def _safe_date(val):
    """Converte para date Python ou None."""
    try:
        if val is None: return None
        if pd.isna(val): return None
        return val.date() if hasattr(val, 'date') else val
    except Exception:
        return None


def upsert_activity(data: dict):
    act_id      = _safe_int(data.get('id'))
    parent_id   = _safe_int(data.get('parent_id'))
    start_d     = _safe_date(data.get('start_date'))
    end_d       = _safe_date(data.get('end_date'))
    title       = str(data.get('title', ''))
    desc        = data.get('description') or None
    priority    = data.get('priority', 'Importante não Urgente')
    status      = data.get('status', 'Não iniciado')
    start_time  = data.get('start_time') or None
    end_time    = data.get('end_time')   or None
    event_color = data.get('event_color') or '#3B82F6'
    event_type  = data.get('event_type')  or 'Tarefa'

    rec_group = data.get('recurrence_group_id') or None

    if act_id:
        execute_query("""
            UPDATE activities
            SET title=%s, description=%s, start_date=%s, end_date=%s,
                priority=%s, status=%s, parent_id=%s,
                start_time=%s, end_time=%s, event_color=%s, event_type=%s,
                updated_at=NOW()
            WHERE id=%s
        """, (title, desc, start_d, end_d, priority, status, parent_id,
              start_time, end_time, event_color, event_type, act_id), fetch=False)
    else:
        rows = execute_query("""
            INSERT INTO activities
                (title, description, start_date, end_date, priority, status, parent_id,
                 start_time, end_time, event_color, event_type, recurrence_group_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (title, desc, start_d, end_d, priority, status, parent_id,
              start_time, end_time, event_color, event_type, rec_group))
        return rows[0]['id'] if rows else None


def delete_activity(activity_id: int):
    """Exclui atividade e todos os seus filhos (ON DELETE CASCADE garante netos também)."""
    execute_query("DELETE FROM activities WHERE id=%s", (activity_id,), fetch=False)


def delete_recurrence_group_activities(group_id: str):
    """Exclui todas as ocorrências de uma série recorrente."""
    execute_query(
        "DELETE FROM activities WHERE recurrence_group_id::text = %s",
        (str(group_id),), fetch=False,
    )


def get_calendar_events(start_date, end_date) -> pd.DataFrame:
    """
    Retorna atividades com start_time definido (eventos de calendário)
    dentro do intervalo de datas. Sincronizado bidirecionalmente com a tabela.
    """
    rows = execute_query("""
        SELECT * FROM activities
        WHERE start_date BETWEEN %s AND %s
          AND start_time IS NOT NULL
        ORDER BY start_date, start_time
    """, (start_date, end_date))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# PLANO DE AÇÃO (5W2H)
# ══════════════════════════════════════════════════════════════════════════════

def get_action_plans(only_standalone: bool = False) -> pd.DataFrame:
    """Lista itens do plano 5W2H. Com only_standalone=True, exclui os das
    atividades vinculadas a uma meta (geridos dentro do módulo Metas)."""
    where = "WHERE a.goal_id IS NULL" if only_standalone else ""
    rows = execute_query(f"""
        SELECT ap.*, a.title AS activity_title
        FROM action_plan ap
        LEFT JOIN activities a ON ap.activity_id = a.id
        {where}
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
        return data['id']
    rows = execute_query("""
        INSERT INTO action_plan (activity_id, what, why, who, when_date, where_place, how, how_much, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
    """, (data.get('activity_id'), data.get('what'), data.get('why'), data.get('who'),
           data.get('when_date'), data.get('where_place'), data.get('how'),
           data.get('how_much'), data.get('status', 'Pendente')))
    return rows[0]['id'] if rows else None


def delete_action_plan(plan_id: int):
    execute_query("DELETE FROM action_plan WHERE id=%s", (plan_id,), fetch=False)


# Colunas que a tabela editável (estilo Excel) do módulo Atividades pode
# gravar direto por célula — allowlist fixa (mais ampla que a versão usada
# em Metas, que só edita título/descrição/datas/status de atividades
# vinculadas a uma meta).
ACTIVITY_EDITABLE_FIELDS = {
    "title", "description", "start_date", "end_date",
    "priority", "status", "parent_id",
}


def update_activity_field(activity_id: int, field: str, value):
    """Salva uma célula editada da tabela de Atividades (autosave)."""
    if field not in ACTIVITY_EDITABLE_FIELDS:
        raise ValueError(f"Campo não editável: {field}")
    if field in ("start_date", "end_date"):
        value = value or None
    elif field == "parent_id":
        value = _safe_int(value)
    else:
        value = (value or "").strip() or None
    execute_query(
        f"UPDATE activities SET {field}=%s, updated_at=NOW() WHERE id=%s",
        (value, activity_id), fetch=False,
    )


ACTION_PLAN_EDITABLE_FIELDS = {"activity_id", "what", "why", "who", "when_date", "where_place", "how", "how_much", "status"}


def update_action_plan_field(plan_id: int, field: str, value):
    """Salva uma célula editada da tabela 5W2H (autosave)."""
    if field not in ACTION_PLAN_EDITABLE_FIELDS:
        raise ValueError(f"Campo não editável: {field}")
    if field == "when_date":
        value = value or None
    elif field == "how_much":
        value = _safe_float(value, 0.0) or None
    elif field == "activity_id":
        value = _safe_int(value)
        if value is None:
            raise ValueError("Escolha uma atividade.")
    else:
        value = (value or "").strip() or None
    execute_query(
        f"UPDATE action_plan SET {field}=%s WHERE id=%s",
        (value, plan_id), fetch=False,
    )


# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICAÇÕES
# ══════════════════════════════════════════════════════════════════════════════

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
