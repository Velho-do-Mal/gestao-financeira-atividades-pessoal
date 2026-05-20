"""
pages/saude.py
Página Saúde — Musculação e Nutrição — BK Finanças

Musculação: Divisões → Exercícios → Séries planejadas + Registro do treino + Histórico de carga
Nutrição:   Base de alimentos → Refeições do dia → Itens → Dashboard de macros
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import date, time as dtime
from database.queries_saude import (
    # Musculação
    get_divisions, upsert_division, delete_division,
    get_exercises, upsert_exercise, delete_exercise,
    get_exercise_sets, upsert_exercise_set, delete_exercise_set,
    get_workout_log, get_weight_history, save_workout_log,
    # Nutrição
    get_foods, upsert_food, delete_food,
    get_meals, upsert_meal, delete_meal,
    get_meal_items, add_meal_item, delete_meal_item,
    get_daily_totals, get_macro_goals, save_macro_goals,
    seed_foods_if_empty,
)
from components.styles import page_header

DAYS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo", "Livre"]
MUSCLE_GROUPS = ["Peito", "Costas", "Ombros", "Bíceps", "Tríceps", "Abdômen",
                 "Quadríceps", "Posterior", "Glúteos", "Panturrilha", "Full Body", "Cardio"]
MEAL_NAMES = ["Café da manhã", "Lanche da manhã", "Pré-treino", "Almoço",
              "Lanche da tarde", "Pós-treino", "Jantar", "Ceia"]
PREP_TYPES = ["Cozido", "Grelhado", "Assado", "Frito", "Cru"]


def _reload():
    st.cache_data.clear()
    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
def render():
    page_header("Saúde", "Musculação e Nutrição", "💪")
    seed_foods_if_empty()

    tab_gym, tab_diet = st.tabs(["🏋️ Musculação", "🥗 Nutrição"])
    with tab_gym:  _tab_musculacao()
    with tab_diet: _tab_nutricao()


# ══════════════════════════════════════════════════════════════════════════════
# ABA MUSCULAÇÃO
# ══════════════════════════════════════════════════════════════════════════════

def _tab_musculacao():
    st.markdown("### 🏋️ Minha Ficha de Treino")

    sub = st.radio("", ["📋 Ficha de Treino", "➕ Gerenciar Divisões", "🗓️ Registrar Treino Hoje"],
                   horizontal=True, label_visibility="collapsed", key="gym_sub")

    if sub == "📋 Ficha de Treino":   _view_workout_plan()
    elif sub == "➕ Gerenciar Divisões": _manage_divisions()
    else:                              _register_workout()


# ─── FICHA DE TREINO ──────────────────────────────────────────────────────────

def _view_workout_plan():
    df_divs = get_divisions()
    if df_divs.empty:
        st.info("Nenhuma divisão cadastrada. Clique em **Gerenciar Divisões** para começar.")
        return

    for _, div in df_divs.iterrows():
        day_badge = f" — {div.get('day_of_week', '')}" if div.get('day_of_week') else ""
        muscles   = div.get('muscle_groups', '') or ''
        with st.expander(f"**{div['name']}**{day_badge}  `{muscles}`", expanded=False):
            df_ex = get_exercises(int(div['id']))
            if df_ex.empty:
                st.info("Nenhum exercício. Adicione em Gerenciar Divisões.")
                continue

            for _, ex in df_ex.iterrows():
                df_sets = get_exercise_sets(int(ex['id']))
                equip   = f" · {ex['equipment']}" if ex.get('equipment') else ""
                notes   = f" · _{ex['notes']}_" if ex.get('notes') else ""

                st.markdown(f"**{ex['name']}**{equip}{notes}")

                if df_sets.empty:
                    st.caption("Nenhuma série configurada.")
                else:
                    cols_header = st.columns([1, 2, 2, 3])
                    cols_header[0].markdown("<small>**Série**</small>", unsafe_allow_html=True)
                    cols_header[1].markdown("<small>**Reps**</small>",  unsafe_allow_html=True)
                    cols_header[2].markdown("<small>**Carga (kg)**</small>", unsafe_allow_html=True)
                    cols_header[3].markdown("<small>**Obs**</small>",   unsafe_allow_html=True)
                    for _, s in df_sets.iterrows():
                        rc = st.columns([1, 2, 2, 3])
                        rc[0].markdown(f"<small>{int(s['set_number'])}</small>", unsafe_allow_html=True)
                        rc[1].markdown(f"<small>{int(s['reps']) if s.get('reps') else '—'}</small>", unsafe_allow_html=True)
                        rc[2].markdown(f"<small>{float(s['weight_kg']) if s.get('weight_kg') else '—'}</small>", unsafe_allow_html=True)
                        rc[3].markdown(f"<small>{s.get('notes','')}</small>", unsafe_allow_html=True)

                # Histórico de carga
                df_hist = get_weight_history(int(ex['id']))
                if not df_hist.empty and len(df_hist) > 1:
                    fig = px.line(df_hist, x='log_date', y='max_weight',
                                  title=f"Evolução de carga — {ex['name']}",
                                  labels={'log_date': 'Data', 'max_weight': 'Carga máx. (kg)'},
                                  template='plotly_dark', markers=True)
                    fig.update_layout(height=220, margin=dict(l=0,r=0,t=30,b=0),
                                      paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig, use_container_width=True, key=f"ev_{int(ex['id'])}")

                st.markdown("---")


# ─── GERENCIAR DIVISÕES ───────────────────────────────────────────────────────

def _manage_divisions():
    df_divs = get_divisions()
    left, right = st.columns([1, 1])

    with left:
        st.markdown("#### Divisões de Treino")
        with st.expander("➕ Nova Divisão", expanded=False):
            if '_div_key' not in st.session_state: st.session_state['_div_key'] = 0
            k = st.session_state['_div_key']
            name    = st.text_input("Nome*", placeholder="Ex: Treino A — Peito", key=f"div_n_{k}")
            c1, c2  = st.columns(2)
            day     = c1.selectbox("Dia", ["—"] + DAYS, key=f"div_d_{k}")
            muscles = c2.multiselect("Grupos Musculares", MUSCLE_GROUPS, key=f"div_m_{k}")
            if st.button("💾 Salvar Divisão", key=f"div_btn_{k}", type="primary", use_container_width=True):
                if name.strip():
                    upsert_division(dict(name=name.strip(),
                                        day_of_week=day if day != "—" else None,
                                        muscle_groups=", ".join(muscles) if muscles else None))
                    st.toast("✅ Divisão salva!", icon="✅")
                    st.session_state['_div_key'] += 1
                    _reload()
                else: st.error("Nome obrigatório.")

        if not df_divs.empty:
            for _, div in df_divs.iterrows():
                cc1, cc2 = st.columns([4, 1])
                day_info = f" ({div['day_of_week']})" if div.get('day_of_week') else ""
                cc1.markdown(f"**{div['name']}**{day_info}")
                cc1.caption(div.get('muscle_groups', '') or '')
                if cc2.button("🗑️", key=f"del_div_{div['id']}", help="Excluir"):
                    delete_division(int(div['id']))
                    st.toast("🗑️ Divisão excluída.", icon="🗑️")
                    _reload()

    with right:
        st.markdown("#### Exercícios por Divisão")
        if df_divs.empty:
            st.info("Cadastre uma divisão primeiro.")
            return

        div_map = dict(zip(df_divs['name'], df_divs['id']))
        sel_div = st.selectbox("Divisão", list(div_map.keys()), key="sel_div_manage")
        div_id  = int(div_map[sel_div])

        with st.expander("➕ Novo Exercício", expanded=False):
            if '_ex_key' not in st.session_state: st.session_state['_ex_key'] = 0
            ke = st.session_state['_ex_key']
            ex_name  = st.text_input("Nome*", placeholder="Ex: Supino Reto", key=f"ex_n_{ke}")
            c1e, c2e = st.columns(2)
            equip    = c1e.text_input("Equipamento", placeholder="Barra, Halteres...", key=f"ex_eq_{ke}")
            notes_ex = c2e.text_input("Observações", key=f"ex_obs_{ke}")
            if st.button("💾 Salvar Exercício", key=f"ex_btn_{ke}", type="primary", use_container_width=True):
                if ex_name.strip():
                    upsert_exercise(dict(division_id=div_id, name=ex_name.strip(),
                                        equipment=equip or None, notes=notes_ex or None))
                    st.toast("✅ Exercício salvo!", icon="✅")
                    st.session_state['_ex_key'] += 1
                    _reload()
                else: st.error("Nome obrigatório.")

        df_ex = get_exercises(div_id)
        if df_ex.empty:
            st.info("Nenhum exercício nesta divisão.")
            return

        sel_ex_name = st.selectbox("Exercício para configurar séries",
                                   df_ex['name'].tolist(), key="sel_ex_sets")
        ex_row = df_ex[df_ex['name'] == sel_ex_name].iloc[0]
        ex_id  = int(ex_row['id'])

        # Mostrar/editar exercícios com botão excluir
        with st.expander("📋 Todos os exercícios desta divisão", expanded=False):
            for _, ex in df_ex.iterrows():
                ec1, ec2 = st.columns([4, 1])
                ec1.markdown(f"• **{ex['name']}** {ex.get('equipment','') or ''}")
                if ec2.button("🗑️", key=f"del_ex_{ex['id']}"):
                    delete_exercise(int(ex['id']))
                    st.toast("🗑️ Exercício excluído.", icon="🗑️")
                    _reload()

        # Séries do exercício selecionado
        st.markdown(f"**Séries de: {sel_ex_name}**")
        df_sets = get_exercise_sets(ex_id)

        # Adicionar série
        next_set = int(df_sets['set_number'].max()) + 1 if not df_sets.empty else 1
        with st.expander(f"➕ Adicionar Série {next_set}", expanded=False):
            sc1, sc2 = st.columns(2)
            s_reps   = sc1.number_input("Repetições", 1, 50, 12, key=f"s_reps_{ex_id}")
            s_weight = sc2.number_input("Carga (kg)", 0.0, 500.0, 0.0, step=2.5, key=f"s_wt_{ex_id}")
            s_notes  = st.text_input("Obs da série", key=f"s_obs_{ex_id}")
            if st.button("➕ Adicionar Série", key=f"s_btn_{ex_id}", use_container_width=True):
                upsert_exercise_set(dict(exercise_id=ex_id, set_number=next_set,
                                         reps=int(s_reps), weight_kg=float(s_weight),
                                         notes=s_notes or None))
                st.toast(f"✅ Série {next_set} adicionada!", icon="✅")
                _reload()

        if not df_sets.empty:
            df_sets_show = df_sets[['id','set_number','reps','weight_kg','notes']].copy()
            df_sets_show.insert(0, 'Excluir', False)
            df_sets_show = df_sets_show.rename(columns={
                'set_number': 'Série', 'reps': 'Reps', 'weight_kg': 'Kg', 'notes': 'Obs'})
            edited = st.data_editor(
                df_sets_show, hide_index=True, use_container_width=True, key=f"sets_edit_{ex_id}",
                column_config={
                    "Excluir": st.column_config.CheckboxColumn("🗑️", width="small"),
                    "id":      st.column_config.NumberColumn("ID", disabled=True, width="small"),
                    "Série":   st.column_config.NumberColumn("Série", width="small"),
                    "Reps":    st.column_config.NumberColumn("Reps",  width="small"),
                    "Kg":      st.column_config.NumberColumn("Kg",    format="%.1f"),
                    "Obs":     st.column_config.TextColumn("Obs"),
                })
            c1s, c2s = st.columns(2)
            to_del = edited[edited['Excluir'] == True]['id'].tolist()
            if c1s.button(f"🗑️ Excluir ({len(to_del)})", disabled=len(to_del)==0, use_container_width=True):
                for rid in to_del: delete_exercise_set(int(rid))
                _reload()
            if c2s.button("💾 Salvar Séries", type="primary", use_container_width=True):
                for _, row in edited[edited['Excluir'] == False].iterrows():
                    upsert_exercise_set(dict(id=int(row['id']), exercise_id=ex_id,
                                             set_number=int(row['Série']),
                                             reps=int(row['Reps']) if row.get('Reps') else None,
                                             weight_kg=float(row['Kg']) if row.get('Kg') else None,
                                             notes=row.get('Obs')))
                st.toast("✅ Séries salvas!", icon="✅")
                _reload()


# ─── REGISTRAR TREINO HOJE ────────────────────────────────────────────────────

def _register_workout():
    st.markdown("#### 🗓️ Registrar Treino de Hoje")
    df_divs = get_divisions()
    if df_divs.empty:
        st.info("Cadastre divisões primeiro.")
        return

    log_date = st.date_input("Data do treino", value=date.today(), key="log_date")
    div_map  = dict(zip(df_divs['name'], df_divs['id']))
    sel_div  = st.selectbox("Divisão treinada", list(div_map.keys()), key="sel_div_log")
    div_id   = int(div_map[sel_div])
    df_ex    = get_exercises(div_id)

    if df_ex.empty:
        st.info("Nenhum exercício nesta divisão.")
        return

    st.markdown("---")
    all_log_data = {}

    for _, ex in df_ex.iterrows():
        ex_id   = int(ex['id'])
        df_sets = get_exercise_sets(ex_id)
        df_done = get_workout_log(ex_id, log_date)

        equip = f" · *{ex['equipment']}*" if ex.get('equipment') else ""
        st.markdown(f"**{ex['name']}**{equip}")

        n_sets = max(len(df_sets), 3) if df_sets.empty else len(df_sets)
        log_rows = []

        cols_h = st.columns([1, 2, 2, 3])
        for lbl, h in zip(["Série","Reps feitas","Carga (kg)","Obs"], cols_h):
            h.markdown(f"<small><b>{lbl}</b></small>", unsafe_allow_html=True)

        for i in range(n_sets):
            s_num     = i + 1
            plan_reps = int(df_sets.iloc[i]['reps']) if not df_sets.empty and i < len(df_sets) and df_sets.iloc[i].get('reps') else 0
            plan_wt   = float(df_sets.iloc[i]['weight_kg']) if not df_sets.empty and i < len(df_sets) and df_sets.iloc[i].get('weight_kg') else 0.0
            # Preenche com log anterior se houver
            done_row = df_done[df_done['set_number'] == s_num] if not df_done.empty else pd.DataFrame()
            prev_reps = int(done_row.iloc[0]['reps_done']) if not done_row.empty and done_row.iloc[0].get('reps_done') else plan_reps
            prev_wt   = float(done_row.iloc[0]['weight_done']) if not done_row.empty and done_row.iloc[0].get('weight_done') else plan_wt

            rc = st.columns([1, 2, 2, 3])
            rc[0].markdown(f"<small>**{s_num}**</small>", unsafe_allow_html=True)
            r = rc[1].number_input("", min_value=0, max_value=100, value=prev_reps,
                                    key=f"log_r_{ex_id}_{s_num}", label_visibility="collapsed")
            w = rc[2].number_input("", min_value=0.0, max_value=500.0, value=prev_wt, step=2.5,
                                    key=f"log_w_{ex_id}_{s_num}", label_visibility="collapsed")
            n = rc[3].text_input("", value="", key=f"log_n_{ex_id}_{s_num}", label_visibility="collapsed")
            log_rows.append({"set_number": s_num, "reps_done": r, "weight_done": w, "notes": n})

        all_log_data[ex_id] = log_rows
        st.markdown("---")

    if st.button("💾 Salvar Treino Completo", type="primary", use_container_width=True, key="save_full_log"):
        for ex_id, rows in all_log_data.items():
            save_workout_log(ex_id, log_date, rows)
        st.success("✅ Treino registrado com sucesso!")
        st.balloons()
        _reload()


# ══════════════════════════════════════════════════════════════════════════════
# ABA NUTRIÇÃO
# ══════════════════════════════════════════════════════════════════════════════

def _tab_nutricao():
    st.markdown("### 🥗 Diário Nutricional")

    sub = st.radio("", ["📊 Diário do Dia", "🍽️ Gerenciar Refeições", "🥩 Base de Alimentos", "🎯 Metas"],
                   horizontal=True, label_visibility="collapsed", key="diet_sub")

    if sub == "📊 Diário do Dia":        _daily_dashboard()
    elif sub == "🍽️ Gerenciar Refeições": _manage_meals()
    elif sub == "🥩 Base de Alimentos":  _manage_foods()
    else:                                _macro_goals()


# ─── DASHBOARD DO DIA ─────────────────────────────────────────────────────────

def _daily_dashboard():
    today    = st.date_input("📅 Data", value=date.today(), key="diet_date")
    goals    = get_macro_goals()
    totals   = get_daily_totals(today)

    prot  = float(totals.get('total_protein', 0))
    carbs = float(totals.get('total_carbs',   0))
    fat   = float(totals.get('total_fat',     0))
    kcal  = float(totals.get('total_kcal',    0))

    g_prot  = float(goals.get('protein_g', 150))
    g_carbs = float(goals.get('carbs_g',   250))
    g_fat   = float(goals.get('fat_g',      60))
    g_kcal  = float(goals.get('goal_kcal', 2000))

    # ── KPIs ──────────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    _macro_card(k1, "🔥 Calorias",  f"{kcal:.0f}",  f"/ {g_kcal:.0f} kcal", kcal,  g_kcal,  "#F59E0B")
    _macro_card(k2, "🥩 Proteína",  f"{prot:.1f}g", f"/ {g_prot:.0f}g",     prot,  g_prot,  "#3B82F6")
    _macro_card(k3, "🌾 Carboidrato",f"{carbs:.1f}g",f"/ {g_carbs:.0f}g",   carbs, g_carbs, "#10B981")
    _macro_card(k4, "🥑 Gordura",   f"{fat:.1f}g",  f"/ {g_fat:.0f}g",      fat,   g_fat,   "#8B5CF6")

    st.markdown("---")

    # ── Gráfico pizza de macros ───────────────────────────────────────────────
    if prot + carbs + fat > 0:
        c_pie, c_bar = st.columns([1, 2])
        with c_pie:
            fig_pie = go.Figure(go.Pie(
                labels=["Proteína", "Carbo", "Gordura"],
                values=[prot, carbs, fat],
                marker_colors=["#3B82F6", "#10B981", "#8B5CF6"],
                hole=0.5,
                textinfo='label+percent',
            ))
            fig_pie.update_layout(
                title="Distribuição de Macros",
                height=280, margin=dict(l=0,r=0,t=40,b=0),
                paper_bgcolor='rgba(0,0,0,0)', font_color='#94A3B8',
                showlegend=False,
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        with c_bar:
            macros = ["Proteína", "Carboidrato", "Gordura"]
            atual  = [prot, carbs, fat]
            meta   = [g_prot, g_carbs, g_fat]
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(name="Consumido", x=macros, y=atual,
                                      marker_color=["#3B82F6","#10B981","#8B5CF6"]))
            fig_bar.add_trace(go.Bar(name="Meta",      x=macros, y=meta,
                                      marker_color=["#1E40AF80","#06543080","#4C1D9580"]))
            fig_bar.update_layout(
                barmode='overlay', title="Consumido vs Meta",
                height=280, margin=dict(l=0,r=0,t=40,b=0),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font_color='#94A3B8', yaxis_title="gramas",
            )
            st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("---")

    # ── Refeições do dia ──────────────────────────────────────────────────────
    st.markdown("#### Refeições do dia")
    df_meals = get_meals(today)

    if df_meals.empty:
        st.info("Nenhuma refeição cadastrada para esta data. Vá em **Gerenciar Refeições** para adicionar.")
        return

    for _, meal in df_meals.iterrows():
        meal_id = int(meal['id'])
        df_items = get_meal_items(meal_id)

        m_prot = float(df_items['item_protein'].sum()) if not df_items.empty else 0
        m_carbs= float(df_items['item_carbs'].sum())   if not df_items.empty else 0
        m_fat  = float(df_items['item_fat'].sum())     if not df_items.empty else 0
        m_kcal = float(df_items['item_kcal'].sum())    if not df_items.empty else 0

        header = (f"**{meal['name']}**"
                  f"  `P:{m_prot:.0f}g` `C:{m_carbs:.0f}g` `G:{m_fat:.0f}g` `🔥{m_kcal:.0f}kcal`")

        with st.expander(header, expanded=False):
            if not df_items.empty:
                show_cols = ['food_name','preparation','quantity_g',
                             'item_protein','item_carbs','item_fat','item_kcal']
                df_show = df_items[[c for c in show_cols if c in df_items.columns]].copy()
                df_show = df_show.rename(columns={
                    'food_name':'Alimento','preparation':'Preparo','quantity_g':'Qtd (g)',
                    'item_protein':'P (g)','item_carbs':'C (g)',
                    'item_fat':'G (g)','item_kcal':'kcal'
                })
                st.dataframe(df_show, hide_index=True, use_container_width=True)


def _macro_card(col, title, value, sub, atual, meta, color):
    pct = min(int(atual / meta * 100), 100) if meta > 0 else 0
    status = "✅" if pct >= 90 else ("⚠️" if pct >= 60 else "❌")
    col.markdown(f"""
    <div style="background:#1E293B;border-radius:12px;padding:14px 16px;
                border:1px solid #334155;border-top:3px solid {color}">
        <div style="color:#94A3B8;font-size:12px">{title}</div>
        <div style="color:#F1F5F9;font-size:22px;font-weight:700;margin:4px 0">{value}</div>
        <div style="color:#64748B;font-size:11px">{sub}</div>
        <div style="background:#334155;border-radius:4px;height:6px;margin-top:8px">
            <div style="width:{pct}%;background:{color};height:100%;border-radius:4px"></div>
        </div>
        <div style="color:#64748B;font-size:11px;margin-top:4px">{pct}% {status}</div>
    </div>
    """, unsafe_allow_html=True)


# ─── GERENCIAR REFEIÇÕES ──────────────────────────────────────────────────────

def _manage_meals():
    st.markdown("#### 🍽️ Refeições")
    meal_date = st.date_input("Data", value=date.today(), key="manage_meal_date")

    # Nova refeição
    with st.expander("➕ Nova Refeição", expanded=False,
                     key=f"exp_meal_{st.session_state.get('_meal_key', 0)}"):
        if '_meal_key' not in st.session_state: st.session_state['_meal_key'] = 0
        mk = st.session_state['_meal_key']
        c1, c2 = st.columns(2)
        meal_name = c1.selectbox("Refeição*", MEAL_NAMES + ["Outra"], key=f"mn_{mk}")
        if meal_name == "Outra":
            meal_name = c1.text_input("Nome da refeição", key=f"mn_custom_{mk}")
        meal_time = c2.time_input("Horário", value=None, key=f"mt_{mk}")
        if st.button("➕ Criar Refeição", key=f"meal_btn_{mk}", type="primary", use_container_width=True):
            if meal_name:
                upsert_meal(dict(name=meal_name, meal_time=meal_time, meal_date=meal_date))
                st.toast(f"✅ Refeição '{meal_name}' criada!", icon="✅")
                st.session_state['_meal_key'] += 1
                _reload()

    df_meals = get_meals(meal_date)
    if df_meals.empty:
        st.info("Nenhuma refeição nesta data.")
        return

    # Lista de alimentos para busca
    df_foods = get_foods()
    food_map = {}
    if not df_foods.empty:
        df_foods['display'] = df_foods['name']
        food_map = dict(zip(df_foods['display'], df_foods['id']))

    for _, meal in df_meals.iterrows():
        meal_id = int(meal['id'])
        df_items = get_meal_items(meal_id)
        m_kcal = float(df_items['item_kcal'].sum()) if not df_items.empty else 0

        with st.expander(f"**{meal['name']}** — `{m_kcal:.0f} kcal`", expanded=True):
            # Itens existentes
            if not df_items.empty:
                for _, item in df_items.iterrows():
                    ic1, ic2, ic3, ic4 = st.columns([3, 1, 1, 1])
                    ic1.markdown(f"**{item['food_name']}** {item.get('preparation','')}")
                    ic2.markdown(f"<small>{item['quantity_g']}g</small>", unsafe_allow_html=True)
                    ic3.markdown(f"<small>🔥{item['item_kcal']:.0f}</small>", unsafe_allow_html=True)
                    if ic4.button("🗑️", key=f"del_item_{item['id']}"):
                        delete_meal_item(int(item['id']))
                        st.toast("🗑️ Item removido.", icon="🗑️")
                        _reload()
                st.markdown("---")

            # Adicionar alimento
            st.markdown("**Adicionar alimento:**")
            ac1, ac2, ac3 = st.columns([4, 2, 2])
            search_q = ac1.text_input("🔍 Buscar alimento", key=f"food_search_{meal_id}",
                                       placeholder="Digite para filtrar...")
            df_filtered = get_foods(search_q) if search_q else df_foods
            food_map_f  = dict(zip(df_filtered['name'], df_filtered['id'])) if not df_filtered.empty else {}
            sel_food = ac1.selectbox("Alimento", ["— Selecione —"] + list(food_map_f.keys()),
                                      key=f"sel_food_{meal_id}", label_visibility="collapsed")
            qty = ac2.number_input("Qtd (g)", 1.0, 2000.0, 100.0, step=10.0, key=f"food_qty_{meal_id}")

            # Preview nutricional
            if sel_food != "— Selecione —" and sel_food in food_map_f:
                fid = food_map_f[sel_food]
                frow = df_filtered[df_filtered['id'] == fid].iloc[0]
                pv = float(frow['protein_g']) * qty / 100
                cv = float(frow['carbs_g'])   * qty / 100
                gv = float(frow['fat_g'])     * qty / 100
                kv = (pv * 4 + cv * 4 + gv * 9)
                ac3.markdown(f"""
                <div style="background:#1E293B;border-radius:8px;padding:8px 12px;font-size:12px">
                    🔥 {kv:.0f} kcal<br>
                    P:{pv:.1f}g · C:{cv:.1f}g · G:{gv:.1f}g
                </div>
                """, unsafe_allow_html=True)

            if st.button("➕ Adicionar", key=f"add_food_btn_{meal_id}", use_container_width=True):
                if sel_food != "— Selecione —" and sel_food in food_map_f:
                    add_meal_item(meal_id, int(food_map_f[sel_food]), float(qty))
                    st.toast(f"✅ {sel_food} adicionado!", icon="✅")
                    _reload()
                else:
                    st.warning("Selecione um alimento.")

            # Excluir refeição
            if st.button(f"🗑️ Excluir refeição '{meal['name']}'",
                         key=f"del_meal_{meal_id}", use_container_width=True):
                delete_meal(meal_id)
                st.toast("🗑️ Refeição excluída.", icon="🗑️")
                _reload()


# ─── BASE DE ALIMENTOS ────────────────────────────────────────────────────────

def _manage_foods():
    st.markdown("#### 🥩 Base de Alimentos")
    st.info("Valores nutricionais por **100g**. Calorias calculadas automaticamente (P×4 + C×4 + G×9).")

    with st.expander("➕ Novo Alimento", expanded=False):
        if '_food_key' not in st.session_state: st.session_state['_food_key'] = 0
        fk = st.session_state['_food_key']
        c1, c2 = st.columns(2)
        f_name = c1.text_input("Nome*", placeholder="Ex: Frango peito grelhado", key=f"fn_{fk}")
        f_prep = c2.selectbox("Preparo", PREP_TYPES, key=f"fp_{fk}")
        c3, c4, c5 = st.columns(3)
        f_prot  = c3.number_input("Proteína (g)",     0.0, 200.0, 0.0, step=0.5, key=f"fpr_{fk}")
        f_carbs = c4.number_input("Carboidrato (g)",  0.0, 200.0, 0.0, step=0.5, key=f"fca_{fk}")
        f_fat   = c5.number_input("Gordura (g)",      0.0, 200.0, 0.0, step=0.5, key=f"ffa_{fk}")
        kcal_preview = f_prot * 4 + f_carbs * 4 + f_fat * 9
        st.caption(f"Calorias: **{kcal_preview:.0f} kcal**/100g")
        if st.button("💾 Salvar Alimento", key=f"fbtn_{fk}", type="primary", use_container_width=True):
            if f_name.strip():
                upsert_food(dict(name=f_name.strip(), preparation=f_prep,
                                  protein_g=f_prot, carbs_g=f_carbs, fat_g=f_fat))
                st.toast("✅ Alimento salvo!", icon="✅")
                st.session_state['_food_key'] += 1
                _reload()
            else: st.error("Nome obrigatório.")

    # Busca e tabela
    search_q = st.text_input("🔍 Buscar na base", placeholder="Digite parte do nome...", key="food_db_search")
    df_foods = get_foods(search_q) if search_q else get_foods()

    if df_foods.empty:
        st.info("Nenhum alimento encontrado.")
        return

    st.markdown(f"**{len(df_foods)} alimento(s)**")
    show_cols = ['id','name','preparation','protein_g','carbs_g','fat_g']
    existing  = [c for c in show_cols if c in df_foods.columns]
    df_show   = df_foods[existing].copy()
    df_show.insert(0, 'Excluir', False)
    df_show['kcal'] = (df_show['protein_g']*4 + df_show['carbs_g']*4 + df_show['fat_g']*9).round(0)
    df_show = df_show.rename(columns={
        'name':'Alimento','preparation':'Preparo',
        'protein_g':'P (g)','carbs_g':'C (g)','fat_g':'G (g)','kcal':'kcal'
    })
    edited = st.data_editor(
        df_show, hide_index=True, use_container_width=True, height=500, key="foods_editor",
        column_config={
            "Excluir":  st.column_config.CheckboxColumn("🗑️", width="small"),
            "id":       st.column_config.NumberColumn("ID", disabled=True, width="small"),
            "Alimento": st.column_config.TextColumn("Alimento"),
            "Preparo":  st.column_config.SelectboxColumn("Preparo", options=PREP_TYPES, width="small"),
            "P (g)":    st.column_config.NumberColumn("P (g)", format="%.1f"),
            "C (g)":    st.column_config.NumberColumn("C (g)", format="%.1f"),
            "G (g)":    st.column_config.NumberColumn("G (g)", format="%.1f"),
            "kcal":     st.column_config.NumberColumn("kcal", disabled=True, format="%.0f"),
        })

    to_del = edited[edited['Excluir'] == True]['id'].tolist()
    c1f, c2f = st.columns(2)
    if c1f.button(f"🗑️ Excluir ({len(to_del)})", disabled=len(to_del)==0, use_container_width=True):
        for rid in to_del: delete_food(int(rid))
        st.toast(f"🗑️ {len(to_del)} excluído(s).", icon="🗑️")
        _reload()
    if c2f.button("💾 Salvar Edições", type="primary", use_container_width=True):
        for _, row in edited[edited['Excluir'] == False].iterrows():
            upsert_food(dict(id=int(row['id']), name=row['Alimento'], preparation=row['Preparo'],
                              protein_g=float(row['P (g)']), carbs_g=float(row['C (g)']),
                              fat_g=float(row['G (g)'])))
        st.toast("✅ Alimentos atualizados!", icon="✅")
        _reload()


# ─── METAS DE MACROS ──────────────────────────────────────────────────────────

def _macro_goals():
    st.markdown("#### 🎯 Metas Diárias de Macros")
    goals = get_macro_goals()

    st.markdown("""
    <div style="background:#1E293B;border-radius:10px;padding:14px 18px;
                margin-bottom:16px;border-left:4px solid #F59E0B">
        <b style="color:#FCD34D">Como calcular sua meta?</b><br>
        <span style="color:#94A3B8;font-size:13px">
        • <b>Proteína:</b> 1.6–2.2g × peso corporal (kg)<br>
        • <b>Carboidrato:</b> 3–6g × peso corporal (kg) (atletas)<br>
        • <b>Gordura:</b> 0.8–1.2g × peso corporal (kg)<br>
        • <b>Calorias:</b> Proteína×4 + Carboidrato×4 + Gordura×9
        </span>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    weight = c1.number_input("Seu peso corporal (kg)", 40.0, 200.0, 80.0, step=0.5, key="goal_wt")

    st.markdown("**Configure suas metas diárias:**")
    g1, g2, g3, g4 = st.columns(4)
    g_prot  = g1.number_input("🥩 Proteína (g)",    0.0, 500.0,
                                float(goals.get('protein_g', 150)), step=5.0, key="g_prot")
    g_carbs = g2.number_input("🌾 Carboidrato (g)", 0.0, 800.0,
                                float(goals.get('carbs_g', 250)),   step=5.0, key="g_carbs")
    g_fat   = g3.number_input("🥑 Gordura (g)",     0.0, 300.0,
                                float(goals.get('fat_g', 60)),      step=2.5, key="g_fat")
    g_kcal  = g_prot*4 + g_carbs*4 + g_fat*9
    g4.metric("🔥 Total Calorias", f"{g_kcal:.0f} kcal")

    # Sugestão automática baseada no peso
    with st.expander("💡 Calcular meta automaticamente pelo peso"):
        mc1, mc2, mc3 = st.columns(3)
        sug_prot  = round(weight * 2.0, 0)
        sug_carbs = round(weight * 4.0, 0)
        sug_fat   = round(weight * 1.0, 0)
        mc1.metric("Proteína sugerida",    f"{sug_prot:.0f}g",  f"{sug_prot/weight:.1f}g/kg")
        mc2.metric("Carboidrato sugerido", f"{sug_carbs:.0f}g", f"{sug_carbs/weight:.1f}g/kg")
        mc3.metric("Gordura sugerida",     f"{sug_fat:.0f}g",   f"{sug_fat/weight:.1f}g/kg")
        if st.button("↑ Usar valores sugeridos", use_container_width=True):
            save_macro_goals(sug_prot, sug_carbs, sug_fat, sug_prot*4+sug_carbs*4+sug_fat*9)
            st.toast("✅ Metas salvas!", icon="✅")
            _reload()

    if st.button("💾 Salvar Metas", type="primary", use_container_width=True, key="save_goals_btn"):
        save_macro_goals(g_prot, g_carbs, g_fat, g_kcal)
        st.toast("✅ Metas salvas!", icon="✅")
        _reload()
