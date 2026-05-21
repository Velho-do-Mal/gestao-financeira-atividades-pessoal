"""
pages/flow.py
Página Flow — Sessão de trabalho em 3 passos sequenciais

Passo 1: Meditação (YouTube iframe)
Passo 2: Diário do dia anterior
Passo 3: Música + Temporizador de sessão

Aba Registros: diário / semanal / mensal
"""

import streamlit as st
import streamlit.components.v1 as stcomp
import pandas as pd
import plotly.graph_objects as go
import time
import plotly.express as px
from datetime import date, datetime, timedelta

from database.queries_flow import (
    get_diary_entry, save_diary_entry, get_diary_entries,
    save_flow_session,
    get_sessions_daily, get_sessions_weekly, get_sessions_monthly,
    get_flow_summary,
)
from components.styles import page_header

# ── URLs ──────────────────────────────────────────────────────────────────────
MEDITATION_URL = "https://www.youtube.com/embed/3rqOqB0cy9o?autoplay=1&rel=0"
MUSIC_URL      = "https://www.youtube.com/embed/Gon27l58lt8?autoplay=1&loop=1&playlist=Gon27l58lt8&rel=0"


def _reload():
    st.cache_data.clear()
    st.rerun()


# ── Session state helpers ─────────────────────────────────────────────────────

def _ss(key, default=None):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]


def _init_flow_state():
    _ss('flow_step',        1)       # 1, 2 ou 3
    _ss('flow_music_on',    False)
    _ss('flow_timer_state', 'idle')  # idle | running | paused | done
    _ss('flow_started_at',  None)
    _ss('flow_elapsed',     0)       # segundos acumulados
    _ss('flow_pause_count', 0)
    _ss('flow_pause_secs',  0)
    _ss('flow_pause_at',    None)


# ══════════════════════════════════════════════════════════════════════════════
def render():
    page_header("Flow", "Sessão de trabalho profundo", "🌊")
    _init_flow_state()

    tab_flow, tab_records = st.tabs(["🌊 Sessão Flow", "📊 Registros"])
    with tab_flow:    _tab_flow()
    with tab_records: _tab_records()


# ══════════════════════════════════════════════════════════════════════════════
# ABA FLOW — 3 PASSOS
# ══════════════════════════════════════════════════════════════════════════════

def _tab_flow():
    step = st.session_state['flow_step']

    # ── Barra de progresso dos passos ─────────────────────────────────────────
    steps = ["🧘 Meditação", "📓 Diário", "⏱️ Flow"]
    cols  = st.columns(3)
    for i, (col, lbl) in enumerate(zip(cols, steps), start=1):
        if i < step:
            bg, color, border = "#0F3D2E", "#6EE7B7", "#10B981"
        elif i == step:
            bg, color, border = "#1E3A5F", "#93C5FD", "#3B82F6"
        else:
            bg, color, border = "#1E293B", "#475569", "#334155"
        col.markdown(f"""
        <div style="background:{bg};border:1px solid {border};border-radius:10px;
                    padding:10px;text-align:center">
            <div style="color:{color};font-weight:600">{lbl}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if step == 1: _step_meditation()
    elif step == 2: _step_diary()
    elif step == 3: _step_flow_session()


# ─── PASSO 1 — MEDITAÇÃO ─────────────────────────────────────────────────────

def _step_meditation():
    st.markdown("### 🧘 Passo 1 — Meditação")
    st.markdown("Assista à meditação antes de iniciar sua sessão de trabalho.")

    # Iframe do YouTube com autoplay
    stcomp.html(f"""
    <div style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;
                border-radius:12px;background:#000">
        <iframe
            src="{MEDITATION_URL}"
            style="position:absolute;top:0;left:0;width:100%;height:100%;border:0"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media;
                   gyroscope; picture-in-picture"
            allowfullscreen>
        </iframe>
    </div>
    """, height=400)

    st.markdown("<br>", unsafe_allow_html=True)
    st.info("Assista à meditação e clique no botão abaixo quando terminar.")

    if st.button("✅ Concluí a meditação — ir para o Diário",
                 type="primary", use_container_width=True, key="btn_step1"):
        st.session_state['flow_step'] = 2
        st.rerun()


# ─── PASSO 2 — DIÁRIO ────────────────────────────────────────────────────────

def _step_diary():
    st.markdown("### 📓 Passo 2 — Diário do dia anterior")

    yesterday = date.today() - timedelta(days=1)
    existing  = get_diary_entry(yesterday)

    st.markdown(f"**Refletindo sobre:** {yesterday.strftime('%d/%m/%Y (%A)')}"
                .replace('Monday','Segunda').replace('Tuesday','Terça')
                .replace('Wednesday','Quarta').replace('Thursday','Quinta')
                .replace('Friday','Sexta').replace('Saturday','Sábado')
                .replace('Sunday','Domingo'))

    if existing:
        st.success("✅ Você já preencheu o diário de ontem. Pode continuar ou editar.")

    with st.form("form_diary", clear_on_submit=False):
        went_well = st.text_area(
            "🌟 O que foi bem ontem?",
            value=str(existing.get('went_well') or '') if existing else '',
            height=80,
            placeholder="Liste as conquistas, grandes ou pequenas..."
        )
        could_improve = st.text_area(
            "🔧 O que poderia ter sido melhor?",
            value=str(existing.get('could_improve') or '') if existing else '',
            height=80,
            placeholder="Sem julgamentos — apenas observações para crescer..."
        )
        gratitude = st.text_area(
            "🙏 Pelo que sou grato(a)?",
            value=str(existing.get('gratitude') or '') if existing else '',
            height=70,
            placeholder="3 coisas pelas quais você é grato(a)..."
        )
        c1, c2 = st.columns([1, 2])
        day_score = c1.slider(
            "⭐ Nota do dia (1–10)",
            1, 10,
            int(existing.get('day_score') or 7) if existing else 7,
        )
        notes = c2.text_area(
            "📝 Observações livres",
            value=str(existing.get('notes') or '') if existing else '',
            height=70,
            placeholder="Qualquer pensamento adicional..."
        )

        submitted = st.form_submit_button(
            "💾 Salvar diário e iniciar sessão Flow →",
            type="primary", use_container_width=True,
        )

    if submitted:
        save_diary_entry(dict(
            entry_date=yesterday,
            went_well=went_well.strip() or None,
            could_improve=could_improve.strip() or None,
            gratitude=gratitude.strip() or None,
            day_score=day_score,
            notes=notes.strip() or None,
        ))
        st.toast("✅ Diário salvo! Iniciando sessão Flow...", icon="📓")
        st.session_state['flow_step'] = 3
        # Reseta timer para nova sessão
        for k in ['flow_timer_state','flow_started_at','flow_elapsed',
                  'flow_pause_count','flow_pause_secs','flow_pause_at','flow_music_on']:
            st.session_state[k] = {'flow_timer_state':'idle','flow_started_at':None,
                                    'flow_elapsed':0,'flow_pause_count':0,
                                    'flow_pause_secs':0,'flow_pause_at':None,
                                    'flow_music_on':False}[k]
        st.rerun()

    st.markdown("---")
    if st.button("⏭️ Pular diário por hoje", key="skip_diary",
                 help="Você pode preencher depois em Registros"):
        st.session_state['flow_step'] = 3
        st.rerun()


# ─── PASSO 3 — SESSÃO FLOW ───────────────────────────────────────────────────

def _step_flow_session():
    st.markdown("### ⏱️ Passo 3 — Sessão de Flow")

    timer_state = st.session_state['flow_timer_state']
    music_on    = st.session_state['flow_music_on']

    # ── Música (iframe YouTube persistente) ──────────────────────────────────
    if music_on:
        stcomp.html(f"""
        <div style="border-radius:12px;overflow:hidden;margin-bottom:12px">
            <iframe
                id="music_player"
                src="{MUSIC_URL}"
                style="width:100%;height:80px;border:0"
                allow="accelerometer; autoplay; clipboard-write;
                       encrypted-media; gyroscope; picture-in-picture"
                allowfullscreen>
            </iframe>
        </div>
        """, height=90)
    else:
        st.markdown("""
        <div style="background:#1E293B;border-radius:12px;padding:14px 18px;
                    border:1px dashed #334155;text-align:center;color:#475569;
                    margin-bottom:12px">
            🎵 Música pausada
        </div>
        """, unsafe_allow_html=True)

    # ── Botão de música ───────────────────────────────────────────────────────
    if st.button("🎵 Ligar música" if not music_on else "🔇 Desligar música",
                 key="btn_music", use_container_width=True):
        st.session_state['flow_music_on'] = not music_on
        st.rerun()

    st.markdown("---")

    # ── Display do timer ──────────────────────────────────────────────────────
    elapsed = int(st.session_state['flow_elapsed'])
    if timer_state == 'running' and st.session_state['flow_started_at']:
        elapsed += int((datetime.now() - st.session_state['flow_started_at']).total_seconds())

    hours   = elapsed // 3600
    minutes = (elapsed % 3600) // 60
    seconds = elapsed % 60
    timer_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    pause_count = st.session_state['flow_pause_count']
    pause_secs  = st.session_state['flow_pause_secs']

    # Cor do timer por estado
    timer_color = {
        'idle':    '#475569',
        'running': '#10B981',
        'paused':  '#F59E0B',
        'done':    '#3B82F6',
    }.get(timer_state, '#475569')

    st.markdown(f"""
    <div style="text-align:center;padding:24px;background:#0F172A;
                border-radius:16px;border:2px solid {timer_color}33">
        <div style="font-family:monospace;font-size:72px;font-weight:700;
                    color:{timer_color};letter-spacing:6px;
                    text-shadow:0 0 30px {timer_color}66">{timer_str}</div>
        <div style="color:#64748B;font-size:14px;margin-top:8px">
            {'🟢 Em andamento' if timer_state=='running' else
             '🟡 Pausado' if timer_state=='paused' else
             '🔵 Concluído' if timer_state=='done' else
             '⚪ Aguardando início'}
            {f" &nbsp;·&nbsp; {pause_count} pausa(s) · {pause_secs//60}min pausado" if pause_count > 0 else ""}
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Botões de controle ────────────────────────────────────────────────────
    if timer_state == 'idle':
        if st.button("▶️ Iniciar sessão", type="primary",
                     use_container_width=True, key="btn_start"):
            st.session_state['flow_timer_state'] = 'running'
            st.session_state['flow_started_at']  = datetime.now()
            st.session_state['flow_elapsed']     = 0
            st.rerun()

    elif timer_state == 'running':
        c1, c2 = st.columns(2)
        if c1.button("⏸️ Pausar", use_container_width=True, key="btn_pause"):
            now = datetime.now()
            elapsed_new = int(st.session_state['flow_elapsed'] +
                              (now - st.session_state['flow_started_at']).total_seconds())
            st.session_state['flow_elapsed']     = elapsed_new
            st.session_state['flow_timer_state'] = 'paused'
            st.session_state['flow_pause_count'] += 1
            st.session_state['flow_pause_at']    = now
            st.rerun()
        if c2.button("⏹️ Finalizar", use_container_width=True, key="btn_stop"):
            _finalize_session()

        # Atualiza o display a cada 1 segundo (abordagem padrão Streamlit)
        time.sleep(1)
        st.rerun()

    elif timer_state == 'paused':
        c1, c2 = st.columns(2)
        if c1.button("▶️ Retomar", type="primary",
                     use_container_width=True, key="btn_resume"):
            if st.session_state['flow_pause_at']:
                pause_dur = int((datetime.now() - st.session_state['flow_pause_at']).total_seconds())
                st.session_state['flow_pause_secs'] += pause_dur
            st.session_state['flow_timer_state'] = 'running'
            st.session_state['flow_started_at']  = datetime.now()
            st.session_state['flow_pause_at']    = None
            st.rerun()
        if c2.button("⏹️ Finalizar", use_container_width=True, key="btn_stop_paused"):
            _finalize_session()

    elif timer_state == 'done':
        st.success("✅ Sessão concluída e salva!")
        if st.button("🔄 Nova sessão", type="primary",
                     use_container_width=True, key="btn_new_session"):
            st.session_state['flow_step']        = 1
            st.session_state['flow_timer_state'] = 'idle'
            st.session_state['flow_elapsed']     = 0
            st.session_state['flow_started_at']  = None
            st.session_state['flow_pause_count'] = 0
            st.session_state['flow_pause_secs']  = 0
            st.session_state['flow_music_on']    = False
            st.rerun()


def _finalize_session():
    """Salva sessão no banco e transita para estado 'done'."""
    now     = datetime.now()
    elapsed = int(st.session_state['flow_elapsed'])
    if st.session_state['flow_started_at'] and st.session_state['flow_timer_state'] == 'running':
        elapsed += int((now - st.session_state['flow_started_at']).total_seconds())

    st.session_state['flow_elapsed']     = elapsed
    st.session_state['flow_timer_state'] = 'done'
    st.session_state['flow_music_on']    = False

    duration_min = max(1, elapsed // 60)

    # Pede nota da sessão via session_state (exibe form antes de salvar)
    st.session_state['_flow_pending_save'] = dict(
        session_date    = date.today(),
        started_at      = st.session_state['flow_started_at'],
        ended_at        = now,
        duration_minutes= duration_min,
        pause_count     = st.session_state['flow_pause_count'],
        pause_minutes   = st.session_state['flow_pause_secs'] // 60,
    )
    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# ABA REGISTROS
# ══════════════════════════════════════════════════════════════════════════════

def _tab_records():
    # Verifica se há sessão pendente de salvar
    if st.session_state.get('_flow_pending_save'):
        _save_session_form()
        return

    st.markdown("### 📊 Registros de Flow")

    sub = st.radio("", ["📅 Hoje", "📆 Semana", "🗓️ Mês", "📓 Diário"],
                   horizontal=True, label_visibility="collapsed", key="rec_sub")

    today = date.today()
    if sub == "📅 Hoje":      _records_daily(today)
    elif sub == "📆 Semana":  _records_weekly(today)
    elif sub == "🗓️ Mês":    _records_monthly(today)
    else:                     _records_diary()


def _save_session_form():
    """Formulário de nota ao finalizar sessão."""
    data = st.session_state['_flow_pending_save']
    dur  = int(data['duration_minutes'])
    h, m = dur // 60, dur % 60

    st.markdown("### 🏁 Sessão concluída!")
    st.markdown(f"""
    <div style="background:#0F3D2E;border-radius:12px;padding:20px;
                border:1px solid #10B981;margin-bottom:16px;text-align:center">
        <div style="font-size:48px">🎯</div>
        <div style="color:#6EE7B7;font-size:24px;font-weight:700">
            {h}h {m:02d}min de foco profundo
        </div>
        <div style="color:#64748B;margin-top:6px">
            {data['pause_count']} pausa(s) · {data['pause_minutes']}min pausado
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.form("form_save_session"):
        score = st.slider("⭐ Nota da sessão (1–10)", 1, 10, 8)
        notes = st.text_area("📝 Observações da sessão", height=80,
                              placeholder="Como foi a sessão? O que produziu?")
        if st.form_submit_button("💾 Salvar registro", type="primary",
                                  use_container_width=True):
            data['session_score'] = score
            data['notes']         = notes.strip() or None
            save_flow_session(data)
            st.session_state.pop('_flow_pending_save', None)
            st.balloons()
            st.toast("✅ Sessão salva!", icon="🎯")
            st.rerun()


def _records_daily(today: date):
    st.markdown(f"#### Sessões de {today.strftime('%d/%m/%Y')}")
    df = get_sessions_daily(today)
    summary = get_flow_summary()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Sessões totais",  int(summary.get('total_sessions', 0)))
    k2.metric("Horas totais",    f"{int(summary.get('total_minutes',0))//60}h {int(summary.get('total_minutes',0))%60}min")
    k3.metric("Score médio",     summary.get('avg_score', '—'))
    k4.metric("Maior sessão",    f"{int(summary.get('longest_session',0))}min")

    if df.empty:
        st.info("Nenhuma sessão registrada hoje.")
        return

    total_min = int(df['duration_minutes'].sum())
    st.markdown(f"**Total hoje: {total_min//60}h {total_min%60}min em {len(df)} sessão(ões)**")

    df_show = df[['started_at','ended_at','duration_minutes','pause_count','session_score','notes']].copy()
    df_show['started_at']        = pd.to_datetime(df_show['started_at']).dt.strftime('%H:%M')
    df_show['ended_at']          = pd.to_datetime(df_show['ended_at']).dt.strftime('%H:%M')
    df_show['duration_minutes']  = df_show['duration_minutes'].astype(int)
    df_show = df_show.rename(columns={
        'started_at':'Início','ended_at':'Fim',
        'duration_minutes':'Duração (min)','pause_count':'Pausas',
        'session_score':'Score','notes':'Observações',
    })
    st.dataframe(df_show, hide_index=True, use_container_width=True)


def _records_weekly(today: date):
    st.markdown("#### Semana atual")
    df = get_sessions_weekly(today)
    if df.empty:
        st.info("Nenhuma sessão esta semana.")
        return

    df['total_minutes']  = df['total_minutes'].astype(int)
    df['hours']          = df['total_minutes'] / 60
    df['session_date_str']= pd.to_datetime(df['session_date']).dt.strftime('%d/%m (%a)')

    total_week = int(df['total_minutes'].sum())
    days_with  = len(df)
    avg_day    = total_week // days_with if days_with else 0

    k1, k2, k3 = st.columns(3)
    k1.metric("Total na semana", f"{total_week//60}h {total_week%60}min")
    k2.metric("Dias com sessão", f"{days_with} dia(s)")
    k3.metric("Média por dia",   f"{avg_day}min")

    fig = go.Figure(go.Bar(
        x=df['session_date_str'],
        y=df['hours'],
        marker_color='#3B82F6',
        text=[f"{int(m//60)}h{int(m%60):02d}" for m in df['total_minutes']],
        textposition='outside',
    ))
    fig.update_layout(
        title="Horas de Flow por dia",
        xaxis_title="Dia", yaxis_title="Horas",
        height=320, margin=dict(l=0,r=0,t=40,b=0),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font_color='#94A3B8',
    )
    st.plotly_chart(fig, use_container_width=True)


def _records_monthly(today: date):
    st.markdown(f"#### {today.strftime('%B %Y').capitalize()}")
    df = get_sessions_monthly(today)
    if df.empty:
        st.info("Nenhuma sessão este mês.")
        return

    df['total_minutes']   = df['total_minutes'].astype(int)
    df['hours']           = df['total_minutes'] / 60
    df['day']             = pd.to_datetime(df['session_date']).dt.day

    total_month = int(df['total_minutes'].sum())
    days_with   = len(df)
    best_day    = int(df['total_minutes'].max())

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total no mês",   f"{total_month//60}h {total_month%60}min")
    k2.metric("Dias ativos",    f"{days_with} dia(s)")
    k3.metric("Melhor dia",     f"{best_day}min")
    k4.metric("Score médio",    f"{df['avg_score'].mean():.1f}" if 'avg_score' in df.columns else "—")

    fig = px.bar(
        df, x='day', y='hours',
        labels={'day': 'Dia do mês', 'hours': 'Horas'},
        color='hours',
        color_continuous_scale=['#1E3A5F', '#3B82F6', '#10B981'],
        title="Horas de Flow por dia do mês",
        text=[f"{int(m//60)}h{int(m%60):02d}" for m in df['total_minutes']],
    )
    fig.update_traces(textposition='outside')
    fig.update_layout(
        height=340, margin=dict(l=0,r=0,t=40,b=0),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font_color='#94A3B8', showlegend=False, coloraxis_showscale=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _records_diary():
    st.markdown("#### 📓 Entradas do Diário")

    sel_date = st.date_input("Ver / editar data", value=date.today() - timedelta(days=1),
                              key="diary_view_date")
    entry = get_diary_entry(sel_date)

    if entry:
        score = int(entry.get('day_score', 0) or 0)
        star_color = "#10B981" if score >= 8 else ("#F59E0B" if score >= 5 else "#EF4444")
        st.markdown(f"""
        <div style="background:#1E293B;border-radius:12px;padding:16px 20px;
                    border:1px solid #334155;margin-bottom:12px">
            <div style="display:flex;justify-content:space-between">
                <b style="color:#F1F5F9">{sel_date.strftime('%d/%m/%Y')}</b>
                <span style="color:{star_color};font-size:18px">⭐ {score}/10</span>
            </div>
            {"<div style='margin-top:10px'><span style='color:#64748B;font-size:12px'>🌟 O que foi bem</span><br><span style='color:#CBD5E1'>" + str(entry.get('went_well','')) + "</span></div>" if entry.get('went_well') else ""}
            {"<div style='margin-top:8px'><span style='color:#64748B;font-size:12px'>🔧 Melhorias</span><br><span style='color:#CBD5E1'>" + str(entry.get('could_improve','')) + "</span></div>" if entry.get('could_improve') else ""}
            {"<div style='margin-top:8px'><span style='color:#64748B;font-size:12px'>🙏 Gratidão</span><br><span style='color:#CBD5E1'>" + str(entry.get('gratitude','')) + "</span></div>" if entry.get('gratitude') else ""}
            {"<div style='margin-top:8px'><span style='color:#64748B;font-size:12px'>📝 Notas</span><br><span style='color:#CBD5E1'>" + str(entry.get('notes','')) + "</span></div>" if entry.get('notes') else ""}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info(f"Nenhuma entrada para {sel_date.strftime('%d/%m/%Y')}.")

    # Lista das últimas entradas
    st.markdown("---")
    st.markdown("**Últimas 30 entradas:**")
    df = get_diary_entries(30)
    if df.empty:
        st.info("Nenhuma entrada no diário ainda.")
        return

    df_show = df[['entry_date','day_score','went_well','gratitude']].copy()
    df_show['entry_date'] = pd.to_datetime(df_show['entry_date']).dt.strftime('%d/%m/%Y')
    df_show['went_well']  = df_show['went_well'].fillna('').str[:60]
    df_show['gratitude']  = df_show['gratitude'].fillna('').str[:60]
    df_show = df_show.rename(columns={
        'entry_date':'Data','day_score':'Score',
        'went_well':'O que foi bem','gratitude':'Gratidão',
    })
    st.dataframe(df_show, hide_index=True, use_container_width=True)
