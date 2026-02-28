"""
pages/financas.py
Página Finanças — Cadastros, Movimentações, Gerencial, Metas e Dashboards
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import io

from database.queries import (
    get_suppliers, upsert_supplier, delete_supplier,
    get_categories, get_subcategories, upsert_category, upsert_subcategory,
    delete_category, delete_subcategory,
    get_banks, upsert_bank, delete_bank, get_total_initial_balance,
    get_transactions, insert_transaction, update_transaction, delete_transaction,
    get_cashflow_planned_vs_actual,
    get_goals, upsert_goal, delete_goal,
    get_budget, upsert_budget, get_budget_vs_actual,
)
from components.charts import (
    cashflow_bar_line, income_expense_bar, pie_by_category,
    budget_bar_comparison,
)
from components.styles import page_header
from utils.helpers import fmt_currency, fmt_date, df_to_excel_bytes, month_range, card_metric


# ══════════════════════════════════════════════════════════════════
def render():
    page_header("Finanças", "Gestão Financeira Completa", "💼")

    tabs = st.tabs([
        "🗄️ Cadastros",
        "💸 Movimentações",
        "📊 Gerencial",
        "🎯 Metas & Orçamento",
        "📈 Dashboards",
    ])

    with tabs[0]:
        _tab_cadastros()
    with tabs[1]:
        _tab_movimentacoes()
    with tabs[2]:
        _tab_gerencial()
    with tabs[3]:
        _tab_metas_orcamento()
    with tabs[4]:
        _tab_dashboards()


# ══════════════════════════════════════════════════════════════════
# ABA 1 — CADASTROS
# ══════════════════════════════════════════════════════════════════
def _tab_cadastros():
    sub = st.radio(
        "Selecione",
        ["👤 Fornecedores", "🏷️ Categorias", "🏦 Bancos"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if sub == "👤 Fornecedores":
        _cadastro_fornecedores()
    elif sub == "🏷️ Categorias":
        _cadastro_categorias()
    else:
        _cadastro_bancos()


def _cadastro_fornecedores():
    st.markdown("### 👤 Fornecedores")
    df = get_suppliers()

    with st.expander("➕ Novo Fornecedor", expanded=False):
        with st.form("form_supplier"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Nome*", help="Razão social ou nome do fornecedor")
            doc = c2.text_input("CPF / CNPJ")
            email = c1.text_input("E-mail")
            phone = c2.text_input("Telefone")
            address = st.text_area("Endereço", height=60)
            notes = st.text_area("Observações", height=60)
            if st.form_submit_button("💾 Salvar"):
                if name:
                    upsert_supplier(dict(name=name, document=doc, email=email,
                                        phone=phone, address=address, notes=notes))
                    st.success("Fornecedor salvo!")
                    st.rerun()
                else:
                    st.error("Nome é obrigatório.")

    if not df.empty:
        st.dataframe(
            df[['id', 'name', 'document', 'email', 'phone']].rename(columns={
                'id': 'ID', 'name': 'Nome', 'document': 'Doc.',
                'email': 'E-mail', 'phone': 'Telefone',
            }),
            hide_index=True, use_container_width=True,
        )
        del_id = st.number_input("ID para excluir", min_value=0, step=1, key="del_sup")
        if st.button("🗑️ Excluir Fornecedor", key="btn_del_sup"):
            if del_id > 0:
                delete_supplier(int(del_id))
                st.success("Excluído.")
                st.rerun()
    else:
        st.info("Nenhum fornecedor cadastrado.")


def _cadastro_categorias():
    st.markdown("### 🏷️ Categorias e Subcategorias")

    # Formulário de cadastro
    with st.expander("➕ Nova Categoria / Subcategoria", expanded=True):
        with st.form("form_cat"):
            c1, c2, c3 = st.columns(3)
            flow_type = c1.selectbox("Tipo*", ["Entrada", "Saída", "Ambos"])
            cat_name = c2.text_input("Categoria*")
            sub_name = c3.text_input("Subcategoria (opcional)")
            if st.form_submit_button("💾 Cadastrar"):
                if cat_name:
                    upsert_category(flow_type, cat_name)
                    if sub_name:
                        df_cats = get_categories()
                        cat_row = df_cats[(df_cats['name'] == cat_name) & (df_cats['flow_type'] == flow_type)]
                        if not cat_row.empty:
                            upsert_subcategory(int(cat_row.iloc[0]['id']), sub_name)
                    st.success("Categoria cadastrada!")
                    st.rerun()
                else:
                    st.error("Nome da categoria é obrigatório.")

    # Exibição em árvore
    df_cats = get_categories()
    if not df_cats.empty:
        for _, cat in df_cats.iterrows():
            df_sub = get_subcategories(int(cat['id']))
            badge_color = {"Entrada": "#10B981", "Saída": "#EF4444", "Ambos": "#8B5CF6"}.get(cat['flow_type'], "#64748B")
            sub_list = ", ".join(df_sub['name'].tolist()) if not df_sub.empty else "—"
            st.markdown(f"""
            <div style="background:#1E293B;border-radius:8px;padding:12px 16px;margin-bottom:6px;
                        border-left:3px solid {badge_color}">
                <span style="background:{badge_color}22;color:{badge_color};
                             border-radius:4px;padding:2px 8px;font-size:11px;font-weight:600">
                    {cat['flow_type']}
                </span>
                <span style="font-weight:600;color:#E2E8F0;margin-left:10px">{cat['name']}</span>
                <span style="color:#64748B;font-size:12px;margin-left:8px"> → {sub_list}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Nenhuma categoria cadastrada.")


def _cadastro_bancos():
    st.markdown("### 🏦 Bancos e Contas")
    df = get_banks()

    with st.expander("➕ Novo Banco", expanded=False):
        with st.form("form_bank"):
            c1, c2, c3, c4 = st.columns(4)
            name = c1.text_input("Banco*")
            account = c2.text_input("Conta")
            agency = c3.text_input("Agência")
            initial_balance = c4.number_input("Saldo Inicial (R$)", value=0.0, step=0.01)
            if st.form_submit_button("💾 Salvar"):
                if name:
                    upsert_bank(dict(name=name, account=account, agency=agency, initial_balance=initial_balance))
                    st.success("Banco salvo!")
                    st.rerun()
                else:
                    st.error("Nome do banco é obrigatório.")

    if not df.empty:
        st.dataframe(
            df[['id', 'name', 'account', 'agency', 'initial_balance']].rename(columns={
                'id': 'ID', 'name': 'Banco', 'account': 'Conta',
                'agency': 'Agência', 'initial_balance': 'Saldo Inicial',
            }).style.format({'Saldo Inicial': 'R$ {:,.2f}'}),
            hide_index=True, use_container_width=True,
        )
        total = get_total_initial_balance()
        st.markdown(f"**Total Saldo Inicial dos Bancos:** `{fmt_currency(total)}`")
    else:
        st.info("Nenhum banco cadastrado.")


# ══════════════════════════════════════════════════════════════════
# ABA 2 — MOVIMENTAÇÕES
# ══════════════════════════════════════════════════════════════════
def _tab_movimentacoes():
    st.markdown("### 💸 Movimentações Financeiras")

    sub_tabs = st.tabs(["➕ Nova Movimentação", "📅 Recorrências", "📋 Previsto", "✅ Realizado", "📊 Diferença"])

    with sub_tabs[0]:
        _form_movimentacao()
    with sub_tabs[1]:
        _recorrencias_grid()
    with sub_tabs[2]:
        _tabela_previsto()
    with sub_tabs[3]:
        _tabela_realizado()
    with sub_tabs[4]:
        _tabela_diferenca()


def _form_movimentacao():
    st.markdown("#### Nova Movimentação")
    df_cats = get_categories()
    df_banks = get_banks()
    df_suppliers = get_suppliers()

    with st.form("form_transaction", clear_on_submit=True):
        c1, c2 = st.columns(2)
        flow_type = c1.selectbox("Tipo*", ["Saída", "Entrada"])
        description = c2.text_input("Descrição")

        # Categoria filtrada por tipo
        cats = df_cats[df_cats['flow_type'].isin([flow_type, 'Ambos'])] if not df_cats.empty else pd.DataFrame()
        cat_options = dict(zip(cats['name'], cats['id'])) if not cats.empty else {}
        cat_name = c1.selectbox("Categoria", list(cat_options.keys()) if cat_options else ["— Cadastre uma categoria —"])
        cat_id = cat_options.get(cat_name)

        # Subcategoria filtrada
        sub_options = {}
        if cat_id:
            df_sub = get_subcategories(int(cat_id))
            if not df_sub.empty:
                sub_options = dict(zip(df_sub['name'], df_sub['id']))
        sub_name = c2.selectbox("Subcategoria", list(sub_options.keys()) if sub_options else ["— Selecione —"])
        sub_id = sub_options.get(sub_name)

        c3, c4, c5 = st.columns(3)
        value = c3.number_input("Valor (R$)*", min_value=0.0, step=0.01)
        interest = c4.number_input("Juros (R$)", min_value=0.0, step=0.01)
        total_value = value + interest
        c5.metric("Valor Total", fmt_currency(total_value))

        c6, c7, c8 = st.columns(3)
        due_date = c6.date_input("Vencimento*", value=date.today())
        status = c7.selectbox("Status", ["Não pago", "Pago"])
        payment_date = c8.date_input("Data Pagamento", value=None) if status == "Pago" else None

        # Banco e Fornecedor
        bank_options = dict(zip(df_banks['name'], df_banks['id'])) if not df_banks.empty else {}
        sup_options = {f"{r['name']}": r['id'] for _, r in df_suppliers.iterrows()} if not df_suppliers.empty else {}

        c9, c10 = st.columns(2)
        bank_name = c9.selectbox("Banco/Conta", ["— Nenhum —"] + list(bank_options.keys()))
        sup_name = c10.selectbox("Fornecedor", ["— Nenhum —"] + list(sup_options.keys()))
        bank_id = bank_options.get(bank_name)
        sup_id = sup_options.get(sup_name)

        st.markdown("**Recorrência**")
        c_r1, c_r2, c_r3 = st.columns(3)
        is_recurrent = c_r1.selectbox("Recorrente?", ["Não", "Sim"]) == "Sim"
        rec_type = c_r2.selectbox("Tipo", ["Mensal", "Diário", "Anual"]) if is_recurrent else "Mensal"
        rec_months = c_r3.number_input("Qtd. ocorrências", min_value=1, max_value=24, value=12) if is_recurrent else 0

        notes = st.text_area("Observações", height=60)

        submitted = st.form_submit_button("💾 Salvar Movimentação", use_container_width=True)
        if submitted:
            if value <= 0:
                st.error("Valor deve ser maior que zero.")
            else:
                data = dict(
                    flow_type=flow_type, category_id=cat_id, subcategory_id=sub_id,
                    supplier_id=sup_id, bank_id=bank_id, description=description,
                    value=value, interest=interest, due_date=due_date,
                    status=status, payment_date=payment_date,
                    is_recurrent=is_recurrent, recurrence_type=rec_type,
                    notes=notes, is_forecast=True,
                )
                insert_transaction(data, recurrence_months=int(rec_months) if is_recurrent else 0)
                st.success("✅ Movimentação salva com sucesso!")
                st.rerun()


def _recorrencias_grid():
    """Grid de recorrências em 24 colunas de meses."""
    st.markdown("#### 📅 Movimentações Recorrentes")

    df = get_transactions()
    if df.empty:
        st.info("Nenhuma movimentação cadastrada.")
        return

    recurrent = df[df['is_recurrent'] == True] if 'is_recurrent' in df.columns else pd.DataFrame()
    if recurrent.empty:
        st.info("Nenhuma movimentação recorrente cadastrada.")
        return

    # Montar pivot de meses
    months = month_range(24)
    month_labels = [m.strftime("%b/%Y") for m in months]

    pivot_rows = []
    for _, row in recurrent.drop_duplicates(subset=['recurrence_group_id']).iterrows():
        r = {
            'Tipo': row.get('flow_type', ''),
            'Categoria': row.get('category_name', ''),
            'Subcategoria': row.get('subcategory_name', ''),
            'Descrição': row.get('description', ''),
        }
        for m in months:
            key = m.strftime("%b/%Y")
            mask = (
                (df['recurrence_group_id'] == row['recurrence_group_id']) &
                (pd.to_datetime(df['due_date']).dt.to_period('M') == pd.Period(m, freq='M'))
            )
            match = df[mask]
            r[key] = float(match['total_value'].sum()) if not match.empty else 0.0
        pivot_rows.append(r)

    df_pivot = pd.DataFrame(pivot_rows)
    st.dataframe(df_pivot, use_container_width=True, height=400)


def _build_cashflow_table(is_forecast: bool):
    today = date.today().replace(day=1)
    months = [today + relativedelta(months=i) for i in range(24)]
    month_labels = [m.strftime("%b/%Y") for m in months]

    df_cats = get_categories()
    rows = []

    for _, cat in df_cats.iterrows():
        df_subs = get_subcategories(int(cat['id']))
        if df_subs.empty:
            row = {'Tipo': cat['flow_type'], 'Categoria': cat['name'], 'Subcategoria': '—'}
            for m in months:
                df_t = get_transactions(
                    start_date=m,
                    end_date=(m + relativedelta(months=1) - relativedelta(days=1)),
                    flow_type=cat['flow_type'],
                    is_forecast=is_forecast,
                )
                val = float(df_t[df_t['category_id'] == cat['id']]['total_value'].sum()) if not df_t.empty else 0.0
                row[m.strftime("%b/%Y")] = val
            rows.append(row)
        else:
            for _, sub in df_subs.iterrows():
                row = {'Tipo': cat['flow_type'], 'Categoria': cat['name'], 'Subcategoria': sub['name']}
                for m in months:
                    df_t = get_transactions(
                        start_date=m,
                        end_date=(m + relativedelta(months=1) - relativedelta(days=1)),
                        flow_type=cat['flow_type'],
                        is_forecast=is_forecast,
                    )
                    val = float(df_t[df_t['subcategory_id'] == sub['id']]['total_value'].sum()) if not df_t.empty else 0.0
                    row[m.strftime("%b/%Y")] = val
                rows.append(row)

    df_table = pd.DataFrame(rows)
    return df_table, month_labels


def _tabela_previsto():
    st.markdown("#### 📋 Fluxo de Caixa Previsto")
    df_table, month_labels = _build_cashflow_table(is_forecast=True)
    if df_table.empty:
        st.info("Nenhum dado previsto.")
        return

    # Rodapés: Soma Saídas, Soma Entradas, Saldo, Saldo Acumulado
    totals_out = {'Tipo': 'TOTAL SAÍDAS', 'Categoria': '', 'Subcategoria': ''}
    totals_in = {'Tipo': 'TOTAL ENTRADAS', 'Categoria': '', 'Subcategoria': ''}
    saldo = {'Tipo': 'SALDO MÊS', 'Categoria': '', 'Subcategoria': ''}
    saldo_acc = {'Tipo': 'SALDO ACUMULADO', 'Categoria': '', 'Subcategoria': ''}
    initial = get_total_initial_balance()
    acc = initial

    for m in month_labels:
        out_val = float(df_table[df_table['Tipo'] == 'Saída'][m].sum()) if m in df_table.columns else 0
        in_val = float(df_table[df_table['Tipo'] == 'Entrada'][m].sum()) if m in df_table.columns else 0
        totals_out[m] = out_val
        totals_in[m] = in_val
        bal = in_val - out_val
        saldo[m] = bal
        acc += bal
        saldo_acc[m] = acc

    df_footer = pd.DataFrame([totals_out, totals_in, saldo, saldo_acc])
    df_display = pd.concat([df_table, df_footer], ignore_index=True)
    st.dataframe(df_display, use_container_width=True, height=500)


def _tabela_realizado():
    st.markdown("#### ✅ Fluxo de Caixa Realizado")
    df_table, month_labels = _build_cashflow_table(is_forecast=False)
    if df_table.empty:
        st.info("Nenhum dado realizado.")
        return

    totals_out = {'Tipo': 'TOTAL SAÍDAS', 'Categoria': '', 'Subcategoria': ''}
    totals_in = {'Tipo': 'TOTAL ENTRADAS', 'Categoria': '', 'Subcategoria': ''}
    saldo = {'Tipo': 'SALDO MÊS', 'Categoria': '', 'Subcategoria': ''}
    saldo_acc = {'Tipo': 'SALDO ACUMULADO', 'Categoria': '', 'Subcategoria': ''}
    initial = get_total_initial_balance()
    acc = initial

    for m in month_labels:
        out_val = float(df_table[df_table['Tipo'] == 'Saída'][m].sum()) if m in df_table.columns else 0
        in_val = float(df_table[df_table['Tipo'] == 'Entrada'][m].sum()) if m in df_table.columns else 0
        totals_out[m] = out_val
        totals_in[m] = in_val
        bal = in_val - out_val
        saldo[m] = bal
        acc += bal
        saldo_acc[m] = acc

    df_footer = pd.DataFrame([totals_out, totals_in, saldo, saldo_acc])
    df_display = pd.concat([df_table, df_footer], ignore_index=True)
    st.dataframe(df_display, use_container_width=True, height=500)


def _tabela_diferenca():
    st.markdown("#### 📊 Diferença: Previsto × Realizado")
    df_prev, month_labels = _build_cashflow_table(is_forecast=True)
    df_real, _ = _build_cashflow_table(is_forecast=False)

    if df_prev.empty and df_real.empty:
        st.info("Sem dados para comparação.")
        return

    df_diff = df_prev[['Tipo', 'Categoria', 'Subcategoria']].copy()
    for m in month_labels:
        p = df_prev[m].fillna(0) if m in df_prev.columns else 0
        r = df_real[m].fillna(0) if m in df_real.columns else 0
        df_diff[m] = p - r

    st.dataframe(df_diff, use_container_width=True, height=500)


# ══════════════════════════════════════════════════════════════════
# ABA 3 — GERENCIAL
# ══════════════════════════════════════════════════════════════════
def _tab_gerencial():
    st.markdown("### 📊 Gerencial")

    # Filtros
    col_f1, col_f2, col_f3 = st.columns(3)
    start_date = col_f1.date_input("Data Início", value=date.today().replace(day=1))
    end_date = col_f2.date_input("Data Fim", value=date.today())
    view_mode = col_f3.selectbox("Visualização", ["Previsto", "Realizado", "Ambos"])

    is_forecast = {"Previsto": True, "Realizado": False, "Ambos": None}.get(view_mode)

    df_all = get_transactions(start_date=start_date, end_date=end_date)
    if is_forecast is not None:
        df_all = df_all[df_all['is_forecast'] == is_forecast] if not df_all.empty else df_all

    # ── Fluxo de Caixa ─────────────────────────────────────────────
    st.markdown("#### 💹 Fluxo de Caixa")
    if not df_all.empty:
        df_all['month'] = pd.to_datetime(df_all['due_date']).dt.to_period('M').dt.to_timestamp()
        df_cf = df_all.groupby(['month', 'flow_type'])['total_value'].sum().reset_index()
        df_pivot = df_cf.pivot(index='month', columns='flow_type', values='total_value').fillna(0).reset_index()
        df_pivot.columns.name = None
        df_pivot['month'] = df_pivot['month'].dt.strftime('%b/%Y')
        if 'Entrada' not in df_pivot.columns:
            df_pivot['Entrada'] = 0
        if 'Saída' not in df_pivot.columns:
            df_pivot['Saída'] = 0
        df_pivot = df_pivot.rename(columns={'Entrada': 'income', 'Saída': 'expense'})
        fig_cf = income_expense_bar(df_pivot, f"Fluxo de Caixa — {view_mode}")
        st.plotly_chart(fig_cf, use_container_width=True)
    else:
        st.info("Sem dados para o período selecionado.")

    # ── Pizza por Categoria ─────────────────────────────────────────
    st.markdown("#### 🥧 Distribuição por Categoria")
    col_p1, col_p2 = st.columns(2)

    with col_p1:
        df_prev_cat = get_transactions(start_date=start_date, end_date=end_date, is_forecast=True)
        if not df_prev_cat.empty:
            df_prev_cat = df_prev_cat[df_prev_cat['flow_type'] == 'Saída']
            df_cat_prev = df_prev_cat.groupby('category_name')['total_value'].sum().reset_index()
            df_cat_prev.columns = ['category', 'value']
            fig_p = pie_by_category(df_cat_prev, "Previsto por Categoria")
            st.plotly_chart(fig_p, use_container_width=True, config={"displayModeBar": False})

    with col_p2:
        df_real_cat = get_transactions(start_date=start_date, end_date=end_date, is_forecast=False)
        if not df_real_cat.empty:
            df_real_cat = df_real_cat[df_real_cat['flow_type'] == 'Saída']
            df_cat_real = df_real_cat.groupby('category_name')['total_value'].sum().reset_index()
            df_cat_real.columns = ['category', 'value']
            fig_a = pie_by_category(df_cat_real, "Realizado por Categoria")
            st.plotly_chart(fig_a, use_container_width=True, config={"displayModeBar": False})

    # ── DRE ────────────────────────────────────────────────────────
    st.markdown("#### 📑 DRE — Demonstrativo de Resultado")
    if not df_all.empty:
        total_in = float(df_all[df_all['flow_type'] == 'Entrada']['total_value'].sum())
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

    # ── Extrato ─────────────────────────────────────────────────────
    st.markdown("#### 📜 Extrato do Período")
    if not df_all.empty:
        cols_show = ['due_date', 'flow_type', 'category_name', 'subcategory_name',
                     'description', 'total_value', 'status', 'bank_name']
        existing = [c for c in cols_show if c in df_all.columns]
        df_show = df_all[existing].copy()
        df_show['due_date'] = pd.to_datetime(df_show['due_date']).dt.strftime('%d/%m/%Y')

        st.dataframe(
            df_show.rename(columns={
                'due_date': 'Vencimento', 'flow_type': 'Tipo', 'category_name': 'Categoria',
                'subcategory_name': 'Subcategoria', 'description': 'Descrição',
                'total_value': 'Valor Total', 'status': 'Status', 'bank_name': 'Banco',
            }).style.format({'Valor Total': 'R$ {:,.2f}'}),
            use_container_width=True, hide_index=True
        )

        col_xl, _ = st.columns([1, 3])
        with col_xl:
            excel_bytes = df_to_excel_bytes(df_show)
            st.download_button(
                "📥 Exportar Excel",
                data=excel_bytes,
                file_name=f"extrato_{start_date}_{end_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    else:
        st.info("Nenhum lançamento no período.")


# ══════════════════════════════════════════════════════════════════
# ABA 4 — METAS & ORÇAMENTO
# ══════════════════════════════════════════════════════════════════
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
        with st.form("form_goal"):
            title = st.text_input("Título da Meta*")
            c1, c2 = st.columns(2)
            specific = c1.text_area("S — Específica (O quê?)", height=80)
            measurable = c2.text_area("M — Mensurável (Quanto?)", height=80)
            achievable = c1.text_area("A — Atingível (Como?)", height=80)
            relevant = c2.text_area("R — Relevante (Por quê?)", height=80)
            c3, c4, c5 = st.columns(3)
            time_bound = c3.date_input("T — Prazo")
            target_value = c4.number_input("Valor Alvo (R$)", min_value=0.0)
            current_value = c5.number_input("Valor Atual (R$)", min_value=0.0)
            status = st.selectbox("Status", ["Em andamento", "Concluída", "Cancelada"])
            if st.form_submit_button("💾 Salvar Meta"):
                if title:
                    upsert_goal(dict(title=title, specific=specific, measurable=measurable,
                                    achievable=achievable, relevant=relevant, time_bound=time_bound,
                                    target_value=target_value, current_value=current_value, status=status))
                    st.success("Meta salva!")
                    st.rerun()
                else:
                    st.error("Título é obrigatório.")

    df = get_goals()
    if not df.empty:
        for _, goal in df.iterrows():
            status_color = {"Em andamento": "#F59E0B", "Concluída": "#10B981", "Cancelada": "#EF4444"}.get(goal['status'], "#64748B")
            pct = min(float(goal.get('current_value', 0)) / max(float(goal.get('target_value', 1)), 1) * 100, 100)

            with st.expander(f"{'✅' if goal['status'] == 'Concluída' else '🎯'} {goal['title']} — {goal['status']}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"""
                    | | |
                    |---|---|
                    | **Específica** | {goal.get('specific') or '—'} |
                    | **Mensurável** | {goal.get('measurable') or '—'} |
                    | **Atingível** | {goal.get('achievable') or '—'} |
                    | **Relevante** | {goal.get('relevant') or '—'} |
                    | **Prazo** | {fmt_date(goal.get('time_bound'))} |
                    """)
                with col2:
                    st.metric("Progresso", f"{pct:.0f}%")
                    st.progress(pct / 100)
                    st.metric("Alvo", fmt_currency(float(goal.get('target_value') or 0)))
                    st.metric("Atual", fmt_currency(float(goal.get('current_value') or 0)))

                if st.button(f"🗑️ Excluir", key=f"del_goal_{goal['id']}"):
                    delete_goal(int(goal['id']))
                    st.rerun()
    else:
        st.info("Nenhuma meta cadastrada.")


def _orcamento():
    st.markdown("#### 💰 Orçamento Mensal (24 meses)")

    months = month_range(24)
    month_labels = [m.strftime("%b/%Y") for m in months]

    df_cats = get_categories()
    if df_cats.empty:
        st.info("Cadastre categorias primeiro.")
        return

    selected_month_label = st.selectbox("Mês para editar", month_labels)
    selected_month = months[month_labels.index(selected_month_label)]

    df_budget = get_budget(selected_month)

    # Formulário de orçamento
    with st.form("form_budget"):
        st.markdown(f"**Orçamento — {selected_month_label}**")
        budget_data = {}
        for _, cat in df_cats.iterrows():
            existing = df_budget[df_budget['category_id'] == cat['id']]['planned_value'].values
            current = float(existing[0]) if len(existing) > 0 else 0.0
            badge = {"Entrada": "📥", "Saída": "📤", "Ambos": "↔️"}.get(cat['flow_type'], "")
            val = st.number_input(
                f"{badge} {cat['name']} ({cat['flow_type']})",
                min_value=0.0, value=current, step=0.01, key=f"bud_{cat['id']}_{selected_month_label}"
            )
            budget_data[int(cat['id'])] = val

        if st.form_submit_button("💾 Salvar Orçamento"):
            for cat_id, val in budget_data.items():
                upsert_budget(cat_id, None, selected_month, val)
            st.success("Orçamento salvo!")
            st.rerun()

    # Comparação Orçado x Realizado
    st.markdown("---")
    df_compare = get_budget_vs_actual(selected_month)
    if not df_compare.empty:
        fig = budget_bar_comparison(df_compare)
        st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════
# ABA 5 — DASHBOARDS
# ══════════════════════════════════════════════════════════════════
def _tab_dashboards():
    st.markdown("### 📈 Dashboards Gerenciais")

    today = date.today()
    c1, c2 = st.columns(2)
    start_d = c1.date_input("De", value=today.replace(month=1, day=1))
    end_d = c2.date_input("Até", value=today)

    df = get_transactions(start_date=start_d, end_date=end_d)

    if df.empty:
        st.warning("Nenhum dado no período selecionado.")
        return

    # KPIs
    total_in = float(df[df['flow_type'] == 'Entrada']['total_value'].sum())
    total_out = float(df[df['flow_type'] == 'Saída']['total_value'].sum())
    resultado = total_in - total_out
    inadimplencia = float(df[(df['flow_type'] == 'Saída') & (df['status'] == 'Não pago')
                              & (pd.to_datetime(df['due_date']).dt.date < today)]['total_value'].sum())

    kc1, kc2, kc3, kc4 = st.columns(4)
    with kc1: card_metric("Total Receitas", fmt_currency(total_in), "", "#10B981", "📥")
    with kc2: card_metric("Total Despesas", fmt_currency(total_out), "", "#EF4444", "📤")
    with kc3: card_metric("Resultado", fmt_currency(resultado), "", "#3B82F6" if resultado >= 0 else "#EF4444", "💹")
    with kc4: card_metric("Inadimplência", fmt_currency(inadimplencia), "Contas vencidas", "#F59E0B", "⚠️")

    st.markdown("---")

    # Gráfico de evolução mensal
    df['month'] = pd.to_datetime(df['due_date']).dt.to_period('M').dt.to_timestamp()
    df_monthly = df.groupby(['month', 'flow_type'])['total_value'].sum().reset_index()
    df_piv = df_monthly.pivot(index='month', columns='flow_type', values='total_value').fillna(0).reset_index()
    df_piv.columns.name = None
    df_piv['month'] = df_piv['month'].dt.strftime('%b/%Y')
    if 'Entrada' in df_piv.columns and 'Saída' in df_piv.columns:
        df_piv['balance'] = df_piv['Entrada'] - df_piv['Saída']
        df_piv['accumulated'] = df_piv['balance'].cumsum()
        df_piv = df_piv.rename(columns={'Entrada': 'income', 'Saída': 'expense'})
        fig_main = cashflow_bar_line(df_piv)
        st.plotly_chart(fig_main, use_container_width=True)

    # Pizzas
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        df_out = df[df['flow_type'] == 'Saída'].groupby('category_name')['total_value'].sum().reset_index()
        df_out.columns = ['category', 'value']
        st.plotly_chart(pie_by_category(df_out, "Saídas por Categoria"), use_container_width=True)

    with col_p2:
        df_in = df[df['flow_type'] == 'Entrada'].groupby('category_name')['total_value'].sum().reset_index()
        df_in.columns = ['category', 'value']
        st.plotly_chart(pie_by_category(df_in, "Entradas por Categoria"), use_container_width=True)

    # Dicas de gestão financeira
    st.markdown("---")
    st.markdown("### 💡 Insights & Dicas de Gestão Financeira")

    tips = []
    if inadimplencia > 0:
        tips.append(f"⚠️ **Inadimplência detectada:** Você tem **{fmt_currency(inadimplencia)}** em contas vencidas. Regularize o mais breve possível para evitar juros e impacto no crédito.")
    if resultado < 0:
        tips.append(f"🔴 **Resultado negativo:** Suas despesas superaram as receitas em {fmt_currency(abs(resultado))}. Revise suas categorias de gastos e identifique onde cortar.")
    if total_out > 0 and (total_out / max(total_in, 1)) > 0.8:
        tips.append("🟡 **Comprometimento alto:** Mais de 80% das suas receitas estão comprometidas com despesas. Considere criar uma reserva de emergência.")
    if not tips:
        tips.append(f"✅ **Parabéns!** Seu resultado do período é positivo: {fmt_currency(resultado)}. Continue mantendo o controle!")

    tips += [
        "📌 **Dica:** Revise seu orçamento mensalmente e compare com o realizado.",
        "💡 **Dica:** Estabeleça metas SMART para suas finanças — específicas, mensuráveis e com prazo definido.",
        "🏦 **Dica:** Mantenha ao menos 3 meses de despesas como reserva de emergência.",
        "📊 **Dica:** Categorize todas as suas despesas para identificar gargalos de gastos.",
    ]

    for tip in tips:
        st.markdown(f"""
        <div style="background:#1E293B;border-radius:8px;padding:12px 16px;margin-bottom:8px;
                    border-left:3px solid #3B82F6">
            {tip}
        </div>
        """, unsafe_allow_html=True)

    # Botão imprimir HTML
    if st.button("🖨️ Exportar Dashboard em HTML"):
        st.info("Abra o menu do navegador (Ctrl+P) para imprimir ou salvar como PDF.")
