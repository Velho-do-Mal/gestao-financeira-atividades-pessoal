"""
app.py
BK Gestão Pessoal — Sistema de Gestão Financeira e Atividades
BK Engenharia e Tecnologia
Versão: 2.0.0 | Python 3.13 | Streamlit | PostgreSQL (Neon)

CORREÇÕES v2:
  - notifications_sent: movido de st.session_state (por sessão) para
    st.cache_resource(ttl=3600) → dispara no máximo uma vez por hora
    no servidor, independente de quantas sessões abriam o app.
"""

import streamlit as st
import logging
from datetime import date

# ─── Configuração da página ────────────────────────────────────────────
st.set_page_config(
    page_title="BK Gestão Pessoal",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "BK Gestão Pessoal — Sistema de Gestão Financeira e Atividades\nBK Engenharia e Tecnologia",
    },
)

# ─── Inicialização ─────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── CSS Global ────────────────────────────────────────────────────────
from components.styles import inject_css
inject_css()

# ─── Detecção de viewport (responsivo) ────────────────────────────────
# 1ª carga: redireciona com ?_vw=<px> para capturar largura da tela
# Cargas seguintes: apenas lê o parâmetro, sem overhead
from utils.responsive import init_responsive
init_responsive()

# ─── Migração do banco de dados ────────────────────────────────────────
@st.cache_resource
def init_database():
    """Inicializa o banco de dados (executa uma única vez por processo do servidor)."""
    try:
        from database.migrations import run_migrations, run_health_migrations, run_habits_migrations
        run_migrations()
        run_health_migrations()
        run_habits_migrations()
        return True
    except Exception as e:
        st.error(f"❌ Erro ao inicializar banco de dados: {e}")
        return False


db_ok = init_database()


# ─── Flag de notificações no nível do SERVIDOR ──────────────────────────
# TTL de 3600s: e-mail é disparado no máximo 1× por hora, independente do
# número de usuários/sessões simultâneas. Corrige bug original onde cada nova
# sessão disparava um novo e-mail.
@st.cache_resource(ttl=3600)
def _notification_flag():
    """Estado mutable compartilhado entre sessões (reset automático a cada hora)."""
    return {"sent": False}


if db_ok:
    flag = _notification_flag()
    if not flag["sent"]:
        try:
            from database.queries import get_items_for_notification
            from utils.notifications import notify_due_items
            items = get_items_for_notification()
            if items:
                notify_due_items(list(items))
            flag["sent"] = True
        except Exception as e:
            logger.warning(f"Falha ao verificar notificações: {e}")


# ─── Sidebar de navegação ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center;padding:20px 0 10px 0">
        <div style="font-size:40px">🏠</div>
        <h2 style="margin:8px 0 4px 0;color:#93C5FD;font-size:20px">BK Gestão Pessoal</h2>
        <p style="color:#64748B;font-size:12px;margin:0">BK Engenharia e Tecnologia</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    page = st.radio(
        "Navegação",
        ["🏠 Home", "🏠 Finanças", "📋 Atividades", "💪 Saúde", "🔄 Hábitos"],
        label_visibility="collapsed",
    )

    st.markdown("---")

    if db_ok:
        st.markdown("""
        <div style="display:flex;align-items:center;gap:8px;padding:8px 12px;
                    background:#064E3B22;border-radius:8px;border:1px solid #064E3B">
            <span style="color:#10B981;font-size:10px">●</span>
            <span style="color:#6EE7B7;font-size:12px">Banco conectado</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="display:flex;align-items:center;gap:8px;padding:8px 12px;
                    background:#7F1D1D22;border-radius:8px;border:1px solid #7F1D1D">
            <span style="color:#EF4444;font-size:10px">●</span>
            <span style="color:#FCA5A5;font-size:12px">Banco desconectado</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown(f"""
    <p style="color:#475569;font-size:11px;text-align:center;margin-top:16px">
        {date.today().strftime('%d/%m/%Y')} | v2.0.0
    </p>
    """, unsafe_allow_html=True)


# ─── Roteamento de páginas ─────────────────────────────────────────────
if not db_ok:
    st.error("""
    ⚠️ **Não foi possível conectar ao banco de dados.**

    Verifique as configurações em `.streamlit/secrets.toml`:
    ```toml
    [database]
    url = "postgresql://..."
    ```
    """)
    st.stop()

if page == "🏠 Home":
    from pages.home import render
    render()
elif page == "🏠 Finanças":
    from pages.financas import render
    render()
elif page == "📋 Atividades":
    from pages.atividades import render
    render()
elif page == "💪 Saúde":
    from pages.saude import render
    render()
elif page == "🔄 Hábitos":
    from pages.habitos import render
    render()
