"""
pages/financas.py
Página Finanças — Cadastros, Movimentações, Gerencial, Metas e Dashboards

CORREÇÕES / MELHORIAS v2:
  - _build_cashflow_table: de 700+ queries para 3 queries (elimina loop por mês/categoria)
  - _recorrencias_grid: tabela editável + botão de exclusão de grupo inteiro
  - clear_data_cache() antes de st.rerun() em todos os saves → cache sempre fresco
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import io

from utils.responsive import kpi_row, rcols, is_mobile, get_device, month_count

from database.queries import (
    get_suppliers, upsert_supplier, delete_supplier,
    get_categories, get_subcategories, get_all_subcategories, upsert_category,
    upsert_subcategory, delete_category, delete_subcategory,
    get_banks, upsert_bank, delete_bank, get_total_initial_balance, get_all_bank_balances,
    get_transactions, insert_transaction, update_transaction,
    delete_transaction, delete_recurrence_group,
    get_goals, upsert_goal, delete_goal,
    get_budget, upsert_budget, get_budget_vs_actual,
    clear_data_cache,
)
from components.charts import (
    cashflow_bar_line, income_expense_bar, pie_by_category,
    budget_bar_comparison,
)
from components.styles import page_header
from utils.helpers import fmt_currency, fmt_date, df_to_excel_bytes, month_range, card_metric


# ══════════════════════════════════════════════════════════════════════════════
def render():
    page_header("Finanças", "Gestão Financeira Completa", "💼")

    tabs = st.tabs([
        "🗄️ Cadastros",
        "💸 Movimentações",
        "📊 Gerencial",
        "🎯 Metas & Orçamento",
        "📈 Dashboards",
    ])

    with tabs[0]: _tab_cadastros()
    with tabs[1]: _tab_movimentacoes()
    with tabs[2]: _tab_gerencial()
    with tabs[3]: _tab_metas_orcamento()
    with tabs[4]: _tab_dashboards()


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _save_btn(label="💾 Salvar alterações", key="save"):
    return st.button(label, key=key, type="primary", use_container_width=True)


def _info_edit():
    st.caption("✏️ Clique em qualquer célula para editar. Marque ☑ na coluna **Excluir** e salve para remover.")


def _save_and_reload():
    """Limpa cache e recarrega a página após qualquer escrita no banco."""
    clear_data_cache()
    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# ABA 1 — CADASTROS
# ══════════════════════════════════════════════════════════════════════════════

def _tab_cadastros():
    sub = st.radio(
        "Selecione",
        ["👤 Fornecedores", "🏷️ Categorias", "🏦 Bancos"],
        horizontal=True, label_visibility="collapsed",
    )
    st.markdown("---")
    if sub == "👤 Fornecedores":
        _cadastro_fornecedores()
    elif sub == "🏷️ Categorias":
        _cadastro_categorias()
    else:
        _cadastro_bancos()


# ─── FORNECEDORES ────────────────────────────────────────────────

def _cadastro_fornecedores():
    st.markdown("### 👤 Fornecedores")

    with st.expander("➕ Novo Fornecedor", expanded=False):
        with st.form("form_supplier", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name    = c1.text_input("Nome*")
            doc     = c2.text_input("CPF / CNPJ")
            email   = c1.text_input("E-mail")
            phone   = c2.text_input("Telefone")
            address = st.text_area("Endereço", height=60)
            notes   = st.text_area("Observações", height=60)
            if st.form_submit_button("➕ Adicionar"):
                if name:
                    upsert_supplier(dict(name=name, document=doc, email=email,
                                        phone=phone, address=address, notes=notes))
                    st.success("Fornecedor adicionado!")
                    _save_and_reload()
                else:
                    st.error("Nome é obrigatório.")

    df = get_suppliers()
    if df.empty:
        st.info("Nenhum fornecedor cadastrado.")
        return

    _info_edit()
    cols_edit = ['id', 'name', 'document', 'email', 'phone', 'address', 'notes']
    df_edit = df[cols_edit].copy()
    df_edit.insert(0, 'Excluir', False)
    df_edit = df_edit.rename(columns={
        'name': 'Nome', 'document': 'Doc/CNPJ', 'email': 'E-mail',
        'phone': 'Telefone', 'address': 'Endereço', 'notes': 'Observações',
    })

    edited = st.data_editor(
        df_edit, use_container_width=True, hide_index=True, key="editor_suppliers",
        column_config={
            "id":       st.column_config.NumberColumn("ID", disabled=True, width="small"),
            "Excluir":  st.column_config.CheckboxColumn("🗑️", width="small"),
            "Nome":     st.column_config.TextColumn("Nome", width="medium"),
            "Doc/CNPJ": st.column_config.TextColumn("Doc/CNPJ", width="small"),
            "E-mail":   st.column_config.TextColumn("E-mail", width="medium"),
            "Telefone": st.column_config.TextColumn("Telefone", width="small"),
            "Endereço": st.column_config.TextColumn("Endereço"),
            "Observações": st.column_config.TextColumn("Observações"),
        },
    )

    if _save_btn("💾 Salvar alterações nos fornecedores", "save_sup"):
        to_delete = edited[edited['Excluir'] == True]['id'].tolist()
        for rid in to_delete:
            delete_supplier(int(rid))
        for _, row in edited[edited['Excluir'] == False].iterrows():
            upsert_supplier(dict(
                id=int(row['id']), name=row['Nome'], document=row['Doc/CNPJ'],
                email=row['E-mail'], phone=row['Telefone'],
                address=row['Endereço'], notes=row['Observações'],
            ))
        st.success(f"✅ Salvo! {len(to_delete)} excluído(s).")
        _save_and_reload()


# ─── CATEGORIAS ──────────────────────────────────────────────────

def _cadastro_categorias():
    st.markdown("### 🏷️ Categorias e Subcategorias")
    col_cat, col_sub = st.columns(2)

    with col_cat:
        st.markdown("**Categorias**")
        with st.expander("➕ Nova Categoria", expanded=False):
            with st.form("form_cat_new", clear_on_submit=True):
                c1, c2 = st.columns(2)
                ft = c1.selectbox("Tipo*", ["Entrada", "Saída", "Ambos"])
                cn = c2.text_input("Nome*")
                if st.form_submit_button("➕ Adicionar"):
                    if cn:
                        upsert_category(ft, cn)
                        st.success("Categoria adicionada!")
                        _save_and_reload()
                    else:
                        st.error("Nome obrigatório.")

        df_cats = get_categories()
        if not df_cats.empty:
            _info_edit()
            df_cats_edit = df_cats[['id', 'flow_type', 'name']].copy()
            df_cats_edit.insert(0, 'Excluir', False)
            df_cats_edit = df_cats_edit.rename(columns={'flow_type': 'Tipo', 'name': 'Nome'})

            edited_cats = st.data_editor(
                df_cats_edit, use_container_width=True, hide_index=True, key="editor_cats",
                column_config={
                    "id":      st.column_config.NumberColumn("ID", disabled=True, width="small"),
                    "Excluir": st.column_config.CheckboxColumn("🗑️", width="small"),
                    "Tipo":    st.column_config.SelectboxColumn("Tipo", options=["Entrada", "Saída", "Ambos"]),
                    "Nome":    st.column_config.TextColumn("Nome"),
                },
            )
            if _save_btn("💾 Salvar Categorias", "save_cats"):
                for _, row in edited_cats[edited_cats['Excluir'] == True].iterrows():
                    delete_category(int(row['id']))
                for _, row in edited_cats[edited_cats['Excluir'] == False].iterrows():
                    upsert_category(row['Tipo'], row['Nome'], int(row['id']))
                st.success("Categorias salvas!")
                _save_and_reload()
        else:
            st.info("Nenhuma categoria.")

    with col_sub:
        st.markdown("**Subcategorias**")
        df_cats_all = get_categories()
        cat_map = dict(zip(df_cats_all['name'], df_cats_all['id'])) if not df_cats_all.empty else {}

        with st.expander("➕ Nova Subcategoria", expanded=False):
            with st.form("form_sub_new", clear_on_submit=True):
                cat_sel = st.selectbox("Categoria Pai*", list(cat_map.keys()) if cat_map else ["—"])
                sub_nm  = st.text_input("Nome*")
                if st.form_submit_button("➕ Adicionar"):
                    if sub_nm and cat_sel in cat_map:
                        upsert_subcategory(int(cat_map[cat_sel]), sub_nm)
                        st.success("Subcategoria adicionada!")
                        _save_and_reload()
                    else:
                        st.error("Selecione uma categoria e informe o nome.")

        sub_rows = []
        for cat_name, cat_id in cat_map.items():
            df_sub = get_subcategories(int(cat_id))
            if not df_sub.empty:
                for _, s in df_sub.iterrows():
                    sub_rows.append({'id': s['id'], 'Categoria': cat_name, 'Subcategoria': s['name']})
        if sub_rows:
            df_subs_all = pd.DataFrame(sub_rows)
            df_subs_all.insert(0, 'Excluir', False)
            _info_edit()
            edited_subs = st.data_editor(
                df_subs_all, use_container_width=True, hide_index=True, key="editor_subs",
                column_config={
                    "id":           st.column_config.NumberColumn("ID", disabled=True, width="small"),
                    "Excluir":      st.column_config.CheckboxColumn("🗑️", width="small"),
                    "Categoria":    st.column_config.SelectboxColumn("Categoria", options=list(cat_map.keys())),
                    "Subcategoria": st.column_config.TextColumn("Subcategoria"),
                },
            )
            if _save_btn("💾 Salvar Subcategorias", "save_subs"):
                for _, row in edited_subs[edited_subs['Excluir'] == True].iterrows():
                    delete_subcategory(int(row['id']))
                for _, row in edited_subs[edited_subs['Excluir'] == False].iterrows():
                    new_cat_id = cat_map.get(row['Categoria'])
                    if new_cat_id:
                        upsert_subcategory(int(new_cat_id), row['Subcategoria'], int(row['id']))
                st.success("Subcategorias salvas!")
                _save_and_reload()
        else:
            st.info("Nenhuma subcategoria.")


# ─── BANCOS ──────────────────────────────────────────────────────

def _cadastro_bancos():
    st.markdown("### 🏦 Bancos e Contas")

    with st.expander("➕ Novo Banco", expanded=False):
        with st.form("form_bank", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns(4)
            name    = c1.text_input("Banco*")
            account = c2.text_input("Conta")
            agency  = c3.text_input("Agência")
            initial_balance = c4.number_input("Saldo Inicial (R$)", value=0.0, step=0.01)
            if st.form_submit_button("➕ Adicionar"):
                if name:
                    upsert_bank(dict(name=name, account=account,
                                    agency=agency, initial_balance=initial_balance))
                    st.success("Banco adicionado!")
                    _save_and_reload()
                else:
                    st.error("Nome do banco é obrigatório.")

    # Mostra saldo atual calculado (corrigido — não usa a coluna desatualizada)
    df_balances = get_all_bank_balances()
    if df_balances.empty:
        st.info("Nenhum banco cadastrado.")
        return

    # KPIs de saldo
    total_current = float(df_balances['current_balance'].sum())
    total_initial = float(df_balances['initial_balance'].sum())
    bc1, bc2 = st.columns(2)
    with bc1:
        card_metric("Saldo Inicial Total", fmt_currency(total_initial), icon="🏦")
    with bc2:
        card_metric("Saldo Atual Total", fmt_currency(total_current),
                    delta=f"Movimentação: {fmt_currency(total_current - total_initial)}",
                    color="#10B981" if total_current >= total_initial else "#EF4444", icon="💰")

    st.markdown("**Saldo por conta:**")
    df_bal_show = df_balances[['name', 'account', 'agency', 'initial_balance', 'current_balance']].rename(columns={
        'name': 'Banco', 'account': 'Conta', 'agency': 'Agência',
        'initial_balance': 'Saldo Inicial', 'current_balance': 'Saldo Atual',
    })
    st.dataframe(df_bal_show, use_container_width=True, hide_index=True)

    st.markdown("---")
    _info_edit()
    df = get_banks()
    df_edit = df[['id', 'name', 'account', 'agency', 'initial_balance']].copy()
    df_edit.insert(0, 'Excluir', False)
    df_edit = df_edit.rename(columns={
        'name': 'Banco', 'account': 'Conta',
        'agency': 'Agência', 'initial_balance': 'Saldo Inicial (R$)',
    })
    edited = st.data_editor(
        df_edit, use_container_width=True, hide_index=True, key="editor_banks",
        column_config={
            "id":                st.column_config.NumberColumn("ID", disabled=True, width="small"),
            "Excluir":           st.column_config.CheckboxColumn("🗑️", width="small"),
            "Banco":             st.column_config.TextColumn("Banco"),
            "Conta":             st.column_config.TextColumn("Conta", width="small"),
            "Agência":           st.column_config.TextColumn("Agência", width="small"),
            "Saldo Inicial (R$)": st.column_config.NumberColumn("Saldo Inicial (R$)", format="R$ %.2f"),
        },
    )

    if _save_btn("💾 Salvar alterações nos bancos", "save_banks"):
        for _, row in edited[edited['Excluir'] == True].iterrows():
            delete_bank(int(row['id']))
        for _, row in edited[edited['Excluir'] == False].iterrows():
            upsert_bank(dict(
                id=int(row['id']), name=row['Banco'], account=row['Conta'],
                agency=row['Agência'], initial_balance=float(row['Saldo Inicial (R$)']),
            ))
        st.success("✅ Bancos salvos!")
        _save_and_reload()


# ══════════════════════════════════════════════════════════════════════════════
# ABA 2 — MOVIMENTAÇÕES
# ══════════════════════════════════════════════════════════════════════════════

def _tab_movimentacoes():
    st.markdown("### 💸 Movimentações Financeiras")
    sub_tabs = st.tabs([
        "➕ Nova Movimentação",
        "📝 Lançamentos",
        "📅 Recorrências",
        "📋 Previsto",
        "✅ Realizado",
        "📊 Diferença",
    ])
    with sub_tabs[0]: _form_movimentacao()
    with sub_tabs[1]: _grid_lancamentos()
    with sub_tabs[2]: _recorrencias_grid()
    with sub_tabs[3]: _tabela_previsto()
    with sub_tabs[4]: _tabela_realizado()
    with sub_tabs[5]: _tabela_diferenca()


def _form_movimentacao():
    """
    Formulário de nova movimentação SEM st.form — permite reatividade total.

    Por que não usar st.form:
      Dentro de st.form, trocar um selectbox NÃO dispara rerun imediato,
      então categoria e subcategoria não atualizam ao mudar o Tipo.

    Solução: widgets normais (reativos) + chave de reset (_mov_key) que
    incrementa ao salvar, limpando todos os campos automaticamente.
    """
    st.markdown("#### Nova Movimentação")

    # ── Chave de reset — incrementar após salvar "limpa" todos os widgets ──
    if '_mov_key' not in st.session_state:
        st.session_state['_mov_key'] = 0
    k = st.session_state['_mov_key']  # sufixo único por "sessão de preenchimento"

    df_cats      = get_categories()
    df_banks     = get_banks()
    df_suppliers = get_suppliers()

    # ── Linha 1: Tipo + Descrição ─────────────────────────────────────────
    c1, c2    = st.columns(2)
    flow_type = c1.selectbox("Tipo*", ["Saída", "Entrada"], key=f"mov_ft_{k}")
    description = c2.text_input("Descrição", key=f"mov_desc_{k}")

    # ── Linha 2: Categoria (filtrada por Tipo) + Subcategoria (filtrada por Categoria) ──
    # Reativo: muda imediatamente quando flow_type ou categoria mudam
    cats = (
        df_cats[df_cats['flow_type'].isin([flow_type, 'Ambos'])]
        if not df_cats.empty else pd.DataFrame()
    )
    cat_options = dict(zip(cats['name'], cats['id'])) if not cats.empty else {}
    cat_list    = list(cat_options.keys()) if cat_options else ["— Cadastre categorias —"]

    c3, c4   = st.columns(2)
    cat_name = c3.selectbox("Categoria", cat_list, key=f"mov_cat_{k}")
    cat_id   = cat_options.get(cat_name)

    # Subcategorias filtradas pela categoria selecionada
    sub_options = {}
    if cat_id:
        df_sub = get_subcategories(int(cat_id))
        if not df_sub.empty:
            sub_options = dict(zip(df_sub['name'], df_sub['id']))

    sub_list = list(sub_options.keys()) if sub_options else ["— Sem subcategoria —"]
    sub_name = c4.selectbox("Subcategoria", sub_list, key=f"mov_sub_{k}")
    sub_id   = sub_options.get(sub_name)

    # ── Linha 3: Valores ──────────────────────────────────────────────────
    c5, c6, c7 = st.columns(3)
    value    = c5.number_input("Valor (R$)*", min_value=0.0, step=0.01, key=f"mov_val_{k}")
    interest = c6.number_input("Juros (R$)",  min_value=0.0, step=0.01, key=f"mov_jur_{k}")
    c7.metric("Valor Total", fmt_currency(value + interest))

    # ── Linha 4: Datas + Status ───────────────────────────────────────────
    c8, c9, c10 = st.columns(3)
    due_date    = c8.date_input("Vencimento*", value=date.today(), key=f"mov_due_{k}")
    status      = c9.selectbox("Status", ["Não pago", "Pago"],    key=f"mov_sta_{k}")
    payment_date = (
        c10.date_input("Data Pagamento", value=date.today(), key=f"mov_pay_{k}")
        if status == "Pago" else None
    )

    # ── Linha 5: Banco + Fornecedor ───────────────────────────────────────
    bank_options = dict(zip(df_banks['name'], df_banks['id']))     if not df_banks.empty     else {}
    sup_options2 = {r['name']: r['id'] for _, r in df_suppliers.iterrows()} if not df_suppliers.empty else {}

    c11, c12  = st.columns(2)
    bank_name = c11.selectbox("Banco/Conta", ["— Nenhum —"] + list(bank_options.keys()), key=f"mov_bnk_{k}")
    sup_name  = c12.selectbox("Fornecedor",  ["— Nenhum —"] + list(sup_options2.keys()),  key=f"mov_sup_{k}")
    bank_id   = bank_options.get(bank_name)
    sup_id    = sup_options2.get(sup_name)

    # ── Linha 6: Recorrência ──────────────────────────────────────────────
    st.markdown("**Recorrência**")
    cr1, cr2, cr3 = st.columns(3)
    is_recurrent  = cr1.selectbox("Recorrente?", ["Não", "Sim"],            key=f"mov_rec_{k}") == "Sim"
    rec_type      = cr2.selectbox("Tipo",        ["Mensal", "Diário", "Anual"], key=f"mov_rtp_{k}")
    rec_months    = cr3.number_input("Qtd. ocorrências", 1, 60, 12,         key=f"mov_rmo_{k}")

    # ── Observações ───────────────────────────────────────────────────────
    notes = st.text_area("Observações", height=60, key=f"mov_obs_{k}")

    st.markdown("")  # espaçamento

    # ── Botão de salvar ───────────────────────────────────────────────────
    if st.button("💾 Salvar Movimentação", key=f"mov_btn_{k}",
                 type="primary", use_container_width=True):
        if value <= 0:
            st.error("Valor deve ser maior que zero.")
        else:
            insert_transaction(dict(
                flow_type    = flow_type,
                category_id  = cat_id,
                subcategory_id = sub_id,
                supplier_id  = sup_id,
                bank_id      = bank_id,
                description  = description,
                value        = value,
                interest     = interest,
                due_date     = due_date,
                status       = status,
                payment_date = payment_date,
                is_recurrent = is_recurrent,
                recurrence_type = rec_type,
                notes        = notes,
                is_forecast  = (status != "Pago"),
            ), recurrence_months=int(rec_months) if is_recurrent else 0)

            st.success("✅ Movimentação salva!")
            # Incrementa a chave → todos os widgets acima recebem nova key → reset automático
            st.session_state['_mov_key'] += 1
            _save_and_reload()


def _grid_lancamentos():
    """Grid editável de lançamentos — estilo Excel."""
    st.markdown("#### 📝 Lançamentos (editável)")

    cf1, cf2, cf3 = st.columns(3)
    start_d  = cf1.date_input("De",   value=date.today().replace(day=1), key="lc_start")
    end_d    = cf2.date_input("Até",  value=date.today(),                key="lc_end")
    f_status = cf3.selectbox("Status", ["Todos", "Pago", "Não pago"],   key="lc_stat")

    df = get_transactions(start_date=start_d, end_date=end_d,
                          status=f_status if f_status != "Todos" else None)
    if df.empty:
        st.info("Nenhum lançamento no período.")
        return

    _info_edit()
    df_cats  = get_categories()
    cat_names = ["—"] + df_cats['name'].tolist() if not df_cats.empty else ["—"]

    cols = ['id', 'flow_type', 'category_name', 'subcategory_name',
            'description', 'value', 'interest', 'total_value',
            'due_date', 'payment_date', 'status']
    existing = [c for c in cols if c in df.columns]
    df_edit  = df[existing].copy()
    df_edit['due_date']     = pd.to_datetime(df_edit['due_date']).dt.date
    df_edit['payment_date'] = pd.to_datetime(df_edit['payment_date'], errors='coerce').dt.date
    df_edit.insert(0, 'Excluir', False)
    df_edit = df_edit.rename(columns={
        'flow_type': 'Tipo', 'category_name': 'Categoria',
        'subcategory_name': 'Subcategoria', 'description': 'Descrição',
        'value': 'Valor', 'interest': 'Juros', 'total_value': 'Total',
        'due_date': 'Vencimento', 'payment_date': 'Dt. Pagamento', 'status': 'Status',
    })

    edited = st.data_editor(
        df_edit, use_container_width=True, hide_index=True, key="editor_lancamentos",
        column_config={
            "id":            st.column_config.NumberColumn("ID", disabled=True, width="small"),
            "Excluir":       st.column_config.CheckboxColumn("🗑️", width="small"),
            "Tipo":          st.column_config.SelectboxColumn("Tipo", options=["Entrada", "Saída"]),
            "Categoria":     st.column_config.SelectboxColumn("Categoria", options=cat_names),
            "Subcategoria":  st.column_config.TextColumn("Subcategoria"),
            "Descrição":     st.column_config.TextColumn("Descrição"),
            "Valor":         st.column_config.NumberColumn("Valor",  format="R$ %.2f"),
            "Juros":         st.column_config.NumberColumn("Juros",  format="R$ %.2f"),
            "Total":         st.column_config.NumberColumn("Total",  disabled=True, format="R$ %.2f"),
            "Vencimento":    st.column_config.DateColumn("Vencimento"),
            "Dt. Pagamento": st.column_config.DateColumn("Dt. Pagamento"),
            "Status":        st.column_config.SelectboxColumn("Status", options=["Pago", "Não pago"]),
        },
    )

    if _save_btn("💾 Salvar alterações nos lançamentos", "save_lanc"):
        for _, row in edited[edited['Excluir'] == True].iterrows():
            delete_transaction(int(row['id']))

        df_cats_full = get_categories()
        cat_id_map   = dict(zip(df_cats_full['name'], df_cats_full['id'])) if not df_cats_full.empty else {}

        for _, row in edited[edited['Excluir'] == False].iterrows():
            cat_id = cat_id_map.get(row.get('Categoria'))
            update_transaction(int(row['id']), dict(
                flow_type=row['Tipo'], category_id=cat_id, subcategory_id=None,
                value=float(row.get('Valor', 0)), interest=float(row.get('Juros', 0)),
                due_date=row['Vencimento'], status=row['Status'],
                payment_date=row.get('Dt. Pagamento'), description=row.get('Descrição'),
            ))
        st.success("✅ Lançamentos salvos!")
        _save_and_reload()


# ──────────────────────────────────────────────────────────────────────────────
# RECORRÊNCIAS — REESCRITO v2
# Melhorias: tabela editável por mês + botão de exclusão de grupo inteiro
# ──────────────────────────────────────────────────────────────────────────────

def _recorrencias_grid():
    st.markdown("#### 📅 Movimentações Recorrentes")

    # Busca todos os lançamentos de uma vez (cacheado)
    df = get_transactions()
    if df.empty or 'is_recurrent' not in df.columns:
        st.info("Nenhuma movimentação recorrente cadastrada.")
        return

    recurrent = df[df['is_recurrent'] == True].copy()
    if recurrent.empty:
        st.info("Nenhuma movimentação recorrente cadastrada.")
        return

    months       = month_range(month_count())     # 3 mobile / 6 tablet / 24 desktop
    month_labels = [m.strftime("%b/%Y") for m in months]

    # Adiciona coluna auxiliar de mês formatado
    recurrent['month_str'] = pd.to_datetime(recurrent['due_date']).dt.strftime("%b/%Y")

    # Lookup: (group_id_str, month_str) → row completa do transaction
    tx_lookup: dict = {}
    for _, row in recurrent.iterrows():
        gid = str(row['recurrence_group_id']) if row.get('recurrence_group_id') else None
        if gid is None:
            continue
        key = (gid, row['month_str'])
        tx_lookup[key] = row

    # Grupos únicos (um por linha do pivot)
    groups = (
        recurrent.dropna(subset=['recurrence_group_id'])
        .drop_duplicates(subset=['recurrence_group_id'])
    )
    if groups.empty:
        st.info("Nenhuma recorrência com grupo definido.")
        return

    # ── Resumo estatístico ───────────────────────────────────────
    total_groups = len(groups)
    total_values = recurrent['value'].sum()
    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("Grupos de Recorrência", total_groups)
    sc2.metric("Entradas recorrentes",
               int(recurrent[recurrent['flow_type'] == 'Entrada']['recurrence_group_id']
                   .nunique()))
    sc3.metric("Saídas recorrentes",
               int(recurrent[recurrent['flow_type'] == 'Saída']['recurrence_group_id']
                   .nunique()))
    st.markdown("---")

    # ── Constrói pivot ───────────────────────────────────────────
    pivot_rows = []
    for _, g in groups.iterrows():
        gid = str(g['recurrence_group_id'])
        r = {
            'Excluir Grupo': False,
            'group_id':      gid,
            'Tipo':          g.get('flow_type', ''),
            'Categoria':     g.get('category_name', '') or '',
            'Descrição':     g.get('description', '') or '',
            'Periodicidade': g.get('recurrence_type', 'Mensal'),
        }
        for ml in month_labels:
            key = (gid, ml)
            r[ml] = float(tx_lookup[key]['value']) if key in tx_lookup else 0.0
        pivot_rows.append(r)

    df_pivot = pd.DataFrame(pivot_rows)

    # ── Configuração das colunas ─────────────────────────────────
    col_cfg = {
        'Excluir Grupo': st.column_config.CheckboxColumn(
            "🗑️ Excluir grupo",
            help="Marca para EXCLUIR todas as parcelas deste grupo ao salvar",
            width="small",
        ),
        'group_id':      st.column_config.TextColumn("ID Grupo", disabled=True, width="small"),
        'Tipo':          st.column_config.SelectboxColumn(
                             "Tipo", options=["Entrada", "Saída"], disabled=True, width="small"),
        'Categoria':     st.column_config.TextColumn("Categoria",     disabled=True),
        'Descrição':     st.column_config.TextColumn("Descrição",     disabled=True),
        'Periodicidade': st.column_config.TextColumn("Period.",       disabled=True, width="small"),
    }
    for ml in month_labels:
        col_cfg[ml] = st.column_config.NumberColumn(ml, format="R$ %.2f", min_value=0.0)

    col_order = ['Excluir Grupo', 'Tipo', 'Categoria', 'Descrição', 'Periodicidade'] + month_labels

    # ── Instrução ────────────────────────────────────────────────
    st.info(
        "💡 **Edite valores diretamente** na tabela (cada célula = uma parcela do mês).  "
        "Marque **🗑️ Excluir grupo** para remover TODAS as parcelas de uma recorrência."
    )
    _info_edit()

    edited = st.data_editor(
        df_pivot,
        use_container_width=True,
        height=max(200, min(700, len(pivot_rows) * 42 + 60)),
        hide_index=True,
        key="editor_recorrencias",
        column_config=col_cfg,
        column_order=col_order,
        num_rows="fixed",
    )

    # ── Botão de save ────────────────────────────────────────────
    if st.button("💾 Salvar alterações nas recorrências", key="save_rec",
                 type="primary", use_container_width=True):
        n_changes = 0
        n_deleted = 0

        for _, row in edited.iterrows():
            gid = row['group_id']

            # ── Excluir grupo inteiro ────────────────────────────
            if row.get('Excluir Grupo', False):
                delete_recurrence_group(gid)
                n_deleted += 1
                continue

            # ── Atualizar valores mês a mês ──────────────────────
            for ml in month_labels:
                new_val = float(row.get(ml) or 0.0)
                key = (gid, ml)
                if key not in tx_lookup:
                    continue  # parcela não existe neste mês
                tx_row  = tx_lookup[key]
                orig_val = float(tx_row.get('value') or 0.0)
                if abs(new_val - orig_val) < 0.001:
                    continue  # sem alteração

                update_transaction(int(tx_row['id']), dict(
                    flow_type   = tx_row.get('flow_type'),
                    category_id = tx_row.get('category_id'),
                    subcategory_id = tx_row.get('subcategory_id'),
                    value       = new_val,
                    interest    = float(tx_row.get('interest') or 0),
                    due_date    = tx_row['due_date'],
                    status      = tx_row.get('status', 'Não pago'),
                    payment_date = tx_row.get('payment_date'),
                    description = tx_row.get('description'),
                    is_forecast = tx_row.get('is_forecast', True),
                ))
                n_changes += 1

        if n_changes > 0 or n_deleted > 0:
            msgs = []
            if n_changes: msgs.append(f"✅ {n_changes} valor(es) atualizado(s)")
            if n_deleted: msgs.append(f"🗑️ {n_deleted} grupo(s) excluído(s) com todas as parcelas")
            st.success(" | ".join(msgs))
            _save_and_reload()
        else:
            st.info("Nenhuma alteração detectada.")


# ══════════════════════════════════════════════════════════════════════════════
# TABELAS DE FLUXO DE CAIXA — REESCRITO v2
# PERFORMANCE: de 700+ queries → 3 queries (fetch geral + categorias + subcategorias)
# ══════════════════════════════════════════════════════════════════════════════

def _build_cashflow_table(is_forecast: bool):
    """
    Constrói a tabela pivô de fluxo de caixa.

    ANTES (original): chamava get_transactions() dentro de 2 loops aninhados
                      (24 meses × N categorias × M subcategorias) → 700+ queries.
    AGORA (v2):       busca tudo de uma vez, agrega em pandas → 3 queries.
    """
    today  = date.today().replace(day=1)
    n_months = month_count()                      # 3 mobile / 6 tablet / 24 desktop
    months = [today + relativedelta(months=i) for i in range(n_months)]
    month_labels = [m.strftime("%b/%Y") for m in months]

    period_start = months[0]
    period_end   = months[-1] + relativedelta(months=1) - relativedelta(days=1)

    # ── 3 queries totais (todas cacheadas) ───────────────────────
    df_cats = get_categories()
    df_subs = get_all_subcategories()     # uma query para todas as subcategorias
    df_all  = get_transactions(           # uma query para todos os lançamentos do período
        start_date=period_start,
        end_date=period_end,
        is_forecast=is_forecast,
    )

    if df_cats.empty:
        return pd.DataFrame(), month_labels

    # Pré-processa transações fora dos loops
    if not df_all.empty:
        df_all = df_all.copy()
        df_all['month_str']      = pd.to_datetime(df_all['due_date']).dt.strftime('%b/%Y')
        df_all['category_id']    = pd.to_numeric(df_all['category_id'],    errors='coerce')
        df_all['subcategory_id'] = pd.to_numeric(df_all['subcategory_id'], errors='coerce')
        df_all['total_value']    = pd.to_numeric(df_all['total_value'],    errors='coerce').fillna(0)

    rows = []
    for _, cat in df_cats.iterrows():
        cat_id   = int(cat['id'])
        cat_subs = df_subs[df_subs['category_id'] == cat_id] if not df_subs.empty else pd.DataFrame()

        entries = (
            [(None, '—')]
            if cat_subs.empty
            else [(int(s['id']), s['name']) for _, s in cat_subs.iterrows()]
        )

        for sub_id, sub_name in entries:
            row = {
                'Tipo':          cat['flow_type'],
                'Categoria':     cat['name'],
                'Subcategoria':  sub_name,
            }

            if df_all.empty:
                for ml in month_labels:
                    row[ml] = 0.0
            else:
                # Filtragem em pandas — sem nova query ao banco
                df_cat = df_all[df_all['category_id'] == cat_id]
                if sub_id is not None:
                    df_sub_data = df_cat[df_cat['subcategory_id'] == sub_id]
                else:
                    df_sub_data = df_cat[df_cat['subcategory_id'].isna()]

                if not df_sub_data.empty:
                    agg = df_sub_data.groupby('month_str')['total_value'].sum()
                    for ml in month_labels:
                        row[ml] = float(agg.get(ml, 0.0))
                else:
                    for ml in month_labels:
                        row[ml] = 0.0

            rows.append(row)

    return pd.DataFrame(rows), month_labels


def _render_cashflow_table(df_table, month_labels, label: str):
    if df_table.empty:
        st.info(f"Nenhum dado {label.lower()}.")
        return

    initial = get_total_initial_balance()
    acc = initial

    totals_out = {'Tipo': 'TOTAL SAÍDAS',    'Categoria': '', 'Subcategoria': ''}
    totals_in  = {'Tipo': 'TOTAL ENTRADAS',  'Categoria': '', 'Subcategoria': ''}
    saldo_mes  = {'Tipo': 'SALDO MÊS',       'Categoria': '', 'Subcategoria': ''}
    saldo_acc  = {'Tipo': 'SALDO ACUMULADO', 'Categoria': '', 'Subcategoria': ''}

    for m in month_labels:
        out = float(df_table[df_table['Tipo'] == 'Saída'][m].sum())  if m in df_table.columns else 0
        inc = float(df_table[df_table['Tipo'] == 'Entrada'][m].sum()) if m in df_table.columns else 0
        bal = inc - out
        acc += bal
        totals_out[m] = out
        totals_in[m]  = inc
        saldo_mes[m]  = bal
        saldo_acc[m]  = acc

    df_footer  = pd.DataFrame([totals_out, totals_in, saldo_mes, saldo_acc])
    df_display = pd.concat([df_table, df_footer], ignore_index=True)

    st.dataframe(df_display, use_container_width=True, height=520, hide_index=True)


def _tabela_previsto():
    st.markdown("#### 📋 Fluxo de Caixa Previsto")
    df_table, month_labels = _build_cashflow_table(is_forecast=True)
    _render_cashflow_table(df_table, month_labels, "Previsto")


def _tabela_realizado():
    st.markdown("#### ✅ Fluxo de Caixa Realizado")
    df_table, month_labels = _build_cashflow_table(is_forecast=False)
    _render_cashflow_table(df_table, month_labels, "Realizado")


def _tabela_diferenca():
    st.markdown("#### 📊 Diferença: Previsto × Realizado")
    df_prev, month_labels = _build_cashflow_table(is_forecast=True)
    df_real, _            = _build_cashflow_table(is_forecast=False)
    if df_prev.empty and df_real.empty:
        st.info("Sem dados para comparação.")
        return
    df_diff = df_prev[['Tipo', 'Categoria', 'Subcategoria']].copy()
    for m in month_labels:
        p = df_prev[m].fillna(0) if m in df_prev.columns else 0
        r = df_real[m].fillna(0) if m in df_real.columns else 0
        df_diff[m] = p - r
    st.dataframe(df_diff, use_container_width=True, height=500, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# ABA 3 — GERENCIAL
# ══════════════════════════════════════════════════════════════════════════════

def _tab_gerencial():
    st.markdown("### 📊 Gerencial")
    col_f1, col_f2, col_f3 = st.columns(3)
    start_date = col_f1.date_input("Data Início", value=date.today().replace(day=1))
    end_date   = col_f2.date_input("Data Fim",    value=date.today())
    view_mode  = col_f3.selectbox("Visualização", ["Previsto", "Realizado", "Ambos"])
    is_forecast = {"Previsto": True, "Realizado": False, "Ambos": None}.get(view_mode)

    df_all = get_transactions(start_date=start_date, end_date=end_date)
    if is_forecast is not None and not df_all.empty:
        df_all = df_all[df_all['is_forecast'] == is_forecast]

    st.markdown("#### 💹 Fluxo de Caixa")
    if not df_all.empty:
        df_all['month'] = pd.to_datetime(df_all['due_date']).dt.to_period('M').dt.to_timestamp()
        df_cf  = df_all.groupby(['month', 'flow_type'])['total_value'].sum().reset_index()
        df_piv = df_cf.pivot(index='month', columns='flow_type', values='total_value').fillna(0).reset_index()
        df_piv.columns.name = None
        df_piv['month'] = df_piv['month'].dt.strftime('%b/%Y')
        if 'Entrada' not in df_piv.columns: df_piv['Entrada'] = 0
        if 'Saída'   not in df_piv.columns: df_piv['Saída']   = 0
        df_piv = df_piv.rename(columns={'Entrada': 'income', 'Saída': 'expense'})
        st.plotly_chart(income_expense_bar(df_piv, f"Fluxo de Caixa — {view_mode}"), use_container_width=True)
    else:
        st.info("Sem dados para o período.")

    st.markdown("#### 🥧 Distribuição por Categoria")
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        df_p = get_transactions(start_date=start_date, end_date=end_date, is_forecast=True)
        if not df_p.empty:
            df_p  = df_p[df_p['flow_type'] == 'Saída']
            df_agg = df_p.groupby('category_name')['total_value'].sum().reset_index()
            df_agg.columns = ['category', 'value']
            st.plotly_chart(pie_by_category(df_agg, "Previsto por Categoria"), use_container_width=True)
    with col_p2:
        df_r = get_transactions(start_date=start_date, end_date=end_date, is_forecast=False)
        if not df_r.empty:
            df_r   = df_r[df_r['flow_type'] == 'Saída']
            df_agg2 = df_r.groupby('category_name')['total_value'].sum().reset_index()
            df_agg2.columns = ['category', 'value']
            st.plotly_chart(pie_by_category(df_agg2, "Realizado por Categoria"), use_container_width=True)

    st.markdown("#### 📑 DRE")
    if not df_all.empty:
        total_in  = float(df_all[df_all['flow_type'] == 'Entrada']['total_value'].sum())
        total_out = float(df_all[df_all['flow_type'] == 'Saída']['total_value'].sum())
        resultado = total_in - total_out
        res_color = "#10B981" if resultado >= 0 else "#EF4444"
        st.markdown(f"""
        <div style="background:#1E293B;border-radius:12px;padding:24px;border:1px solid #334155">
            <table style="width:100%;border-collapse:collapse">
                <tr style="border-bottom:1px solid #334155">
                    <td style="padding:10px;color:#94A3B8">Receitas Totais</td>
                    <td style="padding:10px;text-align:right;color:#10B981;font-weight:600">{fmt_currency(total_in)}</td>
                </tr>
                <tr style="border-bottom:1px solid #334155">
                    <td style="padding:10px;color:#94A3B8">(-) Despesas Totais</td>
                    <td style="padding:10px;text-align:right;color:#EF4444;font-weight:600">({fmt_currency(total_out)})</td>
                </tr>
                <tr style="background:#0F172A">
                    <td style="padding:12px;color:#F1F5F9;font-weight:700;font-size:16px">= Resultado Líquido</td>
                    <td style="padding:12px;text-align:right;color:{res_color};font-weight:700;font-size:18px">{fmt_currency(resultado)}</td>
                </tr>
            </table>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("#### 📜 Extrato do Período")
    if not df_all.empty:
        cols_show = ['due_date', 'flow_type', 'category_name', 'subcategory_name',
                     'description', 'total_value', 'status', 'bank_name']
        df_show = df_all[[c for c in cols_show if c in df_all.columns]].copy()
        df_show['due_date'] = pd.to_datetime(df_show['due_date']).dt.strftime('%d/%m/%Y')
        st.dataframe(
            df_show.rename(columns={
                'due_date': 'Vencimento', 'flow_type': 'Tipo', 'category_name': 'Categoria',
                'subcategory_name': 'Subcategoria', 'description': 'Descrição',
                'total_value': 'Valor Total', 'status': 'Status', 'bank_name': 'Banco',
            }).style.format({'Valor Total': 'R$ {:,.2f}'}),
            use_container_width=True, hide_index=True,
        )
        excel_bytes = df_to_excel_bytes(df_show)
        st.download_button(
            "📥 Exportar Excel", data=excel_bytes,
            file_name=f"extrato_{start_date}_{end_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        st.info("Nenhum lançamento no período.")


# ══════════════════════════════════════════════════════════════════════════════
# ABA 4 — METAS & ORÇAMENTO
# ══════════════════════════════════════════════════════════════════════════════

def _tab_metas_orcamento():
    st.markdown("### 🎯 Metas e Orçamento")
    sub = st.radio("Seção", ["🎯 Metas SMART", "💰 Orçamento"], horizontal=True, label_visibility="collapsed")
    if sub == "🎯 Metas SMART":
        _metas_smart()
    else:
        _orcamento()


def _metas_smart():
    st.markdown("#### 🎯 Metas SMART")
    with st.expander("➕ Nova Meta", expanded=False):
        with st.form("form_goal", clear_on_submit=True):
            title = st.text_input("Título da Meta*")
            c1, c2 = st.columns(2)
            specific   = c1.text_area("S — Específica",  height=80)
            measurable = c2.text_area("M — Mensurável",  height=80)
            achievable = c1.text_area("A — Atingível",   height=80)
            relevant   = c2.text_area("R — Relevante",   height=80)
            c3, c4, c5 = st.columns(3)
            time_bound    = c3.date_input("T — Prazo")
            target_value  = c4.number_input("Valor Alvo (R$)",  min_value=0.0)
            current_value = c5.number_input("Valor Atual (R$)", min_value=0.0)
            status = st.selectbox("Status", ["Em andamento", "Concluída", "Cancelada"])
            if st.form_submit_button("💾 Salvar Meta"):
                if title:
                    upsert_goal(dict(title=title, specific=specific, measurable=measurable,
                                    achievable=achievable, relevant=relevant,
                                    time_bound=time_bound, target_value=target_value,
                                    current_value=current_value, status=status))
                    st.success("Meta salva!")
                    _save_and_reload()
                else:
                    st.error("Título é obrigatório.")

    df = get_goals()
    if df.empty:
        st.info("Nenhuma meta cadastrada.")
        return

    _info_edit()
    df_edit = df[['id', 'title', 'target_value', 'current_value', 'time_bound', 'status']].copy()
    df_edit.insert(0, 'Excluir', False)
    df_edit['time_bound'] = pd.to_datetime(df_edit['time_bound'], errors='coerce').dt.date
    df_edit = df_edit.rename(columns={
        'title': 'Meta', 'target_value': 'Alvo (R$)',
        'current_value': 'Atual (R$)', 'time_bound': 'Prazo', 'status': 'Status',
    })
    df_edit['Atual (R$)']  = pd.to_numeric(df_edit['Atual (R$)'],  errors='coerce').fillna(0)
    df_edit['Alvo (R$)']   = pd.to_numeric(df_edit['Alvo (R$)'],   errors='coerce').fillna(0)
    df_edit['% Progresso'] = (
        df_edit['Atual (R$)'] / df_edit['Alvo (R$)'].replace(0, 1) * 100
    ).clip(0, 100).round(1)

    edited = st.data_editor(
        df_edit, use_container_width=True, hide_index=True, key="editor_goals",
        column_config={
            "id":          st.column_config.NumberColumn("ID", disabled=True, width="small"),
            "Excluir":     st.column_config.CheckboxColumn("🗑️", width="small"),
            "Meta":        st.column_config.TextColumn("Meta"),
            "Alvo (R$)":   st.column_config.NumberColumn("Alvo (R$)",  format="R$ %.2f"),
            "Atual (R$)":  st.column_config.NumberColumn("Atual (R$)", format="R$ %.2f"),
            "Prazo":       st.column_config.DateColumn("Prazo"),
            "Status":      st.column_config.SelectboxColumn("Status", options=["Em andamento", "Concluída", "Cancelada"]),
            "% Progresso": st.column_config.ProgressColumn("Progresso", min_value=0, max_value=100, format="%.1f%%"),
        },
    )

    if _save_btn("💾 Salvar Metas", "save_goals"):
        for _, row in edited[edited['Excluir'] == True].iterrows():
            delete_goal(int(row['id']))
        for _, row in edited[edited['Excluir'] == False].iterrows():
            orig = df[df['id'] == row['id']].iloc[0] if not df[df['id'] == row['id']].empty else {}
            upsert_goal(dict(
                id=int(row['id']), title=row['Meta'],
                specific=orig.get('specific'), measurable=orig.get('measurable'),
                achievable=orig.get('achievable'), relevant=orig.get('relevant'),
                time_bound=row['Prazo'], target_value=float(row['Alvo (R$)']),
                current_value=float(row['Atual (R$)']), status=row['Status'],
            ))
        st.success("✅ Metas salvas!")
        _save_and_reload()


def _orcamento():
    st.markdown("#### 💰 Orçamento Mensal (24 meses)")
    months       = month_range(24)
    month_labels = [m.strftime("%b/%Y") for m in months]
    df_cats      = get_categories()
    if df_cats.empty:
        st.info("Cadastre categorias primeiro.")
        return

    selected_label = st.selectbox("Mês para editar", month_labels)
    selected_month = months[month_labels.index(selected_label)]
    df_budget      = get_budget(selected_month)

    rows = []
    for _, cat in df_cats.iterrows():
        if not df_budget.empty and 'category_id' in df_budget.columns:
            existing = df_budget[df_budget['category_id'] == cat['id']]['planned_value'].values
        else:
            existing = []
        rows.append({
            'cat_id':       int(cat['id']),
            'Tipo':         cat['flow_type'],
            'Categoria':    cat['name'],
            'Orçado (R$)':  float(existing[0]) if len(existing) > 0 else 0.0,
        })
    df_bud_edit = pd.DataFrame(rows)

    edited_bud = st.data_editor(
        df_bud_edit, use_container_width=True, hide_index=True,
        key=f"editor_budget_{selected_label}",
        column_config={
            "cat_id":      st.column_config.NumberColumn("ID", disabled=True, width="small"),
            "Tipo":        st.column_config.TextColumn("Tipo",      disabled=True),
            "Categoria":   st.column_config.TextColumn("Categoria", disabled=True),
            "Orçado (R$)": st.column_config.NumberColumn("Orçado (R$)", format="R$ %.2f"),
        },
    )

    if _save_btn(f"💾 Salvar Orçamento — {selected_label}", f"save_bud_{selected_label}"):
        for _, row in edited_bud.iterrows():
            upsert_budget(int(row['cat_id']), None, selected_month, float(row['Orçado (R$)']))
        st.success("✅ Orçamento salvo!")
        _save_and_reload()

    st.markdown("---")
    df_compare = get_budget_vs_actual(selected_month)
    if not df_compare.empty:
        st.plotly_chart(budget_bar_comparison(df_compare), use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# ABA 5 — DASHBOARDS
# ══════════════════════════════════════════════════════════════════════════════

def _tab_dashboards():
    st.markdown("### 📈 Dashboards Gerenciais")
    today = date.today()
    c1, c2  = st.columns(2)
    start_d = c1.date_input("De",  value=today.replace(month=1, day=1))
    end_d   = c2.date_input("Até", value=today)

    df = get_transactions(start_date=start_d, end_date=end_d)
    if df.empty:
        st.warning("Nenhum dado no período.")
        return

    total_in     = float(df[df['flow_type'] == 'Entrada']['total_value'].sum())
    total_out    = float(df[df['flow_type'] == 'Saída']['total_value'].sum())
    resultado    = total_in - total_out
    inadimplencia = float(df[
        (df['flow_type'] == 'Saída') & (df['status'] == 'Não pago') &
        (pd.to_datetime(df['due_date']).dt.date < today)
    ]['total_value'].sum())

    kpi_row([
        dict(label="Total Receitas",  value=fmt_currency(total_in),      delta="", color="#10B981", icon="📥"),
        dict(label="Total Despesas",  value=fmt_currency(total_out),     delta="", color="#EF4444", icon="📤"),
        dict(label="Resultado",       value=fmt_currency(resultado),     delta="",
             color="#3B82F6" if resultado >= 0 else "#EF4444", icon="💹"),
        dict(label="Inadimplência",   value=fmt_currency(inadimplencia), delta="Contas vencidas", color="#F59E0B", icon="⚠️"),
    ])

    st.markdown("---")
    df['month'] = pd.to_datetime(df['due_date']).dt.to_period('M').dt.to_timestamp()
    df_monthly  = df.groupby(['month', 'flow_type'])['total_value'].sum().reset_index()
    df_piv      = df_monthly.pivot(index='month', columns='flow_type', values='total_value').fillna(0).reset_index()
    df_piv.columns.name = None
    df_piv['month'] = df_piv['month'].dt.strftime('%b/%Y')
    if 'Entrada' in df_piv.columns and 'Saída' in df_piv.columns:
        df_piv['balance']     = df_piv['Entrada'] - df_piv['Saída']
        df_piv['accumulated'] = df_piv['balance'].cumsum()
        df_piv = df_piv.rename(columns={'Entrada': 'income', 'Saída': 'expense'})
        st.plotly_chart(cashflow_bar_line(df_piv), use_container_width=True)

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        df_out = df[df['flow_type'] == 'Saída'].groupby('category_name')['total_value'].sum().reset_index()
        df_out.columns = ['category', 'value']
        st.plotly_chart(pie_by_category(df_out, "Saídas por Categoria"), use_container_width=True)
    with col_p2:
        df_in = df[df['flow_type'] == 'Entrada'].groupby('category_name')['total_value'].sum().reset_index()
        df_in.columns = ['category', 'value']
        st.plotly_chart(pie_by_category(df_in, "Entradas por Categoria"), use_container_width=True)

    st.markdown("---")
    st.markdown("### 💡 Insights & Dicas de Gestão Financeira")
    tips = []
    if inadimplencia > 0:
        tips.append(f"⚠️ **Inadimplência detectada:** {fmt_currency(inadimplencia)} em contas vencidas.")
    if resultado < 0:
        tips.append(f"🔴 **Resultado negativo:** Despesas superaram receitas em {fmt_currency(abs(resultado))}.")
    if total_out > 0 and (total_out / max(total_in, 1)) > 0.8:
        tips.append("🟡 **Comprometimento alto:** Mais de 80% das receitas comprometidas.")
    if not tips:
        tips.append(f"✅ **Parabéns!** Resultado positivo: {fmt_currency(resultado)}.")
    tips += [
        "📌 **Dica:** Revise o orçamento mensalmente e compare com o realizado.",
        "💡 **Dica:** Metas SMART ajudam a manter o foco financeiro.",
        "🏦 **Dica:** Mantenha ao menos 3 meses de despesas como reserva de emergência.",
    ]
    for tip in tips:
        st.markdown(f"""
        <div style="background:#1E293B;border-radius:8px;padding:12px 16px;
                    margin-bottom:8px;border-left:3px solid #3B82F6">
            {tip}
        </div>
        """, unsafe_allow_html=True)
