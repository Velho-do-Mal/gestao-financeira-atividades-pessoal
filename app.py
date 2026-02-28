"""
app.py
BK Finance — Sistema de Gestão Financeira e Atividades
BK Engenharia e Tecnologia
Versão: 1.0.0 | Python 3.13 | Streamlit | PostgreSQL (Neon)
"""

import streamlit as st
import logging
from datetime import date

# ─── Configuração da página ────────────────────────────────────────────
st.set_page_config(
    page_title="BK Finance",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "BK Finance — Sistema de Gestão Financeira e Atividades\nBK Engenharia e Tecnologia",
    },
)

# ─── Inicialização ─────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── CSS Global ────────────────────────────────────────────────────────
from components.styles import inject_css
inject_css()

# ─── Migração do banco de dados ────────────────────────────────────────
@st.cache_resource
def init_database():
    """Inicializa o banco de dados (executa uma única vez por sessão do servidor)."""
    try:
        from database.migrations import run_migrations
        run_migrations()
        return True
    except Exception as e:
        st.error(f"❌ Erro ao inicializar banco de dados: {e}")
        return False

db_ok = init_database()

# ─── Verificação de notificações (uma vez por sessão) ──────────────────
if 'notifications_sent' not in st.session_state:
    st.session_state.notifications_sent = False

if db_ok and not st.session_state.notifications_sent:
    try:
        from database.queries import get_items_for_notification
        from utils.notifications import notify_due_items
        items = get_items_for_notification()
        if items:
            notify_due_items(list(items))
        st.session_state.notifications_sent = True
    except Exception as e:
        logger.warning(f"Falha ao verificar notificações: {e}")

# ─── Sidebar de navegação ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center;padding:20px 0 10px 0">
        <div style="font-size:40px">💼</div>
        <h2 style="margin:8px 0 4px 0;color:#93C5FD;font-size:20px">BK Finance</h2>
        <p style="color:#64748B;font-size:12px;margin:0">BK Engenharia e Tecnologia</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

if 'page' not in st.session_state:
    st.session_state.page = "🏠 Home"

    nav_items = [
        ("🏠", "Home"),
        ("💼", "Finanças"),
        ("📋", "Atividades"),
    ]

    for icon, label in nav_items:
        key = f"{icon} {label}"
        is_active = st.session_state.page == key
        btn_style = """
        <style>
        div[data-testid="stButton"] button[kind="secondary"] {
            width: 100%;
            text-align: left;
            background: transparent;
            border: none;
            color: #93C5FD;
            font-size: 15px;
            padding: 10px 16px;
            border-radius: 8px;
            font-weight: 500;
        }
        </style>
        """ if not is_active else ""
        
        active_css = f"""
        <style>
        #btn_{label.lower()} button {{
            background: linear-gradient(135deg, #1E40AF, #2563EB) !important;
            color: white !important;
            border-left: 3px solid #60A5FA !important;
            box-shadow: 0 4px 12px rgba(37,99,235,0.3) !important;
        }}
        </style>
        """ if is_active else ""
        
        st.markdown(active_css, unsafe_allow_html=True)
        if st.button(f"{icon}  {label}", key=f"nav_{label}", use_container_width=True):
            st.session_state.page = key
            st.rerun()

    page = st.session_state.page

    st.markdown("---")

    # Status do banco
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
        {date.today().strftime('%d/%m/%Y')} | v1.0.0
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
elif page == "💼 Finanças":
    from pages.financas import render
    render()
elif page == "📋 Atividades":
    from pages.atividades import render
    render()
