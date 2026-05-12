"""
components/styles.py
Estilos CSS globais do BK Finance
"""

GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap');

/* ─── Reset & Base ───────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

.stApp {
    background: #0F172A;
    color: #F1F5F9;
}


/* ─── Ocultar navegação automática multipage do Streamlit ── */
[data-testid="stSidebarNav"] {
    display: none !important;
}

/* ─── Sidebar ────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%) !important;
    border-right: 1px solid #1E40AF44;
}

section[data-testid="stSidebar"] .stRadio label {
    color: #93C5FD !important;
    padding: 8px 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
    font-weight: 500;
}

section[data-testid="stSidebar"] .stRadio label:hover {
    background: #1E3A8A44;
    color: #60A5FA !important;
}

section[data-testid="stSidebar"] .stRadio [data-testid="stMarkdownContainer"] p {
    color: #93C5FD !important;
}

/* ─── Header / Título ────────────────────────────────────── */
.main-header {
    background: linear-gradient(135deg, #1E3A8A 0%, #1E40AF 50%, #2563EB 100%);
    border-radius: 16px;
    padding: 24px 32px;
    margin-bottom: 24px;
    border: 1px solid #3B82F680;
    box-shadow: 0 8px 32px rgba(59,130,246,0.2);
}

.main-header h1 {
    margin: 0;
    font-size: 28px;
    font-weight: 700;
    color: #F8FAFC;
    letter-spacing: -0.5px;
}

.main-header p {
    margin: 4px 0 0 0;
    color: #93C5FD;
    font-size: 14px;
}

/* ─── Cards de métrica ───────────────────────────────────── */
.metric-card {
    background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 20px;
    transition: transform 0.2s, box-shadow 0.2s;
}

.metric-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.4);
}

/* ─── Tabs ───────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: #1E293B;
    border-radius: 12px;
    padding: 4px;
    gap: 4px;
    border: 1px solid #334155;
}

.stTabs [data-baseweb="tab"] {
    background: transparent;
    color: #94A3B8 !important;
    border-radius: 8px;
    font-weight: 500;
    padding: 8px 16px;
    border: none !important;
}

.stTabs [aria-selected="true"] {
    background: #1E40AF !important;
    color: white !important;
    box-shadow: 0 2px 8px rgba(30,64,175,0.4);
}

/* ─── Botões ─────────────────────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, #1E40AF, #2563EB);
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 8px 20px;
    transition: all 0.2s;
}

.stButton > button:hover {
    background: linear-gradient(135deg, #1D4ED8, #3B82F6);
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(59,130,246,0.3);
}

/* Botão perigo */
.btn-danger > button {
    background: linear-gradient(135deg, #7F1D1D, #DC2626) !important;
}

/* Botão sucesso */
.btn-success > button {
    background: linear-gradient(135deg, #064E3B, #059669) !important;
}

/* ─── Inputs ─────────────────────────────────────────────── */
.stTextInput input, .stNumberInput input, .stSelectbox select,
.stTextArea textarea, .stDateInput input {
    background: #1E293B !important;
    border: 1px solid #334155 !important;
    color: #F1F5F9 !important;
    border-radius: 8px !important;
}

.stTextInput input:focus, .stNumberInput input:focus,
.stTextArea textarea:focus {
    border-color: #3B82F6 !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.15) !important;
}

/* ─── DataFrames / Tabelas ───────────────────────────────── */
.stDataFrame {
    border: 1px solid #334155;
    border-radius: 10px;
    overflow: hidden;
}

/* ─── Alertas ────────────────────────────────────────────── */
.stAlert {
    border-radius: 10px;
    border-left: 4px solid;
}

/* ─── Dividers ───────────────────────────────────────────── */
hr {
    border: none;
    border-top: 1px solid #1E293B;
    margin: 16px 0;
}

/* ─── Tooltip ────────────────────────────────────────────── */
.tooltip-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #1E293B;
    border: 1px solid #334155;
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 12px;
    color: #94A3B8;
    cursor: help;
}

/* ─── Prioridade badges ───────────────────────────────────── */
.priority-uu { color: #FCA5A5; font-weight: 600; }
.priority-iu { color: #FDBA74; font-weight: 600; }
.priority-inu { color: #FDE047; font-weight: 600; }
.priority-nnu { color: #86EFAC; font-weight: 600; }

/* ─── Status badges ──────────────────────────────────────── */
.status-pago { color: #34D399; }
.status-npago { color: #F87171; }
.status-vencido { color: #EF4444; font-weight: 700; }

/* ─── Scrollbar ──────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0F172A; }
::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #475569; }

/* ─── Expander ───────────────────────────────────────────── */
.streamlit-expanderHeader {
    background: #1E293B !important;
    border-radius: 8px !important;
    color: #93C5FD !important;
}

/* ─── AgGrid overrides (dark) ────────────────────────────── */
.ag-theme-streamlit {
    --ag-background-color: #1E293B;
    --ag-header-background-color: #0F172A;
    --ag-odd-row-background-color: #162032;
    --ag-row-hover-color: #1E40AF22;
    --ag-selected-row-background-color: #1E40AF44;
    --ag-header-foreground-color: #93C5FD;
    --ag-foreground-color: #CBD5E1;
    --ag-border-color: #334155;
    --ag-font-size: 13px;
}

/* ─── Pomodoro timer ─────────────────────────────────────── */
.pomodoro-display {
    font-family: 'Space Mono', monospace;
    font-size: 64px;
    font-weight: 700;
    color: #60A5FA;
    text-align: center;
    letter-spacing: 4px;
    text-shadow: 0 0 30px rgba(96,165,250,0.5);
}

/* ─── Atividades indentadas ──────────────────────────────── */
.sub-activity {
    border-left: 3px solid #3B82F6;
    padding-left: 20px;
    margin-left: 20px;
    background: rgba(30,64,175,0.05);
    border-radius: 0 8px 8px 0;
}

/* ══════════════════════════════════════════════════════════
   RESPONSIVIDADE — Media Queries
   Breakpoints: mobile ≤640px | tablet 641-1024px | desktop >1024px
   ══════════════════════════════════════════════════════════ */

/* ─── TABLET (641px – 1024px) ────────────────────────────── */
@media (max-width: 1024px) {

    /* Colunas: permitir quebra de linha */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
    }

    /* 4+ colunas → máximo 2 por linha no tablet */
    [data-testid="stHorizontalBlock"] > [data-testid="column"] {
        min-width: 45% !important;
        flex: 1 1 45% !important;
    }

    /* Header menor */
    .main-header h1 { font-size: 22px !important; }
    .main-header    { padding: 16px 20px !important; }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        min-width: 220px !important;
        max-width: 240px !important;
    }
}

/* ─── MOBILE (≤ 640px) ───────────────────────────────────── */
@media (max-width: 640px) {

    /* Todas as colunas viram 1 coluna */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        gap: 8px !important;
    }
    [data-testid="stHorizontalBlock"] > [data-testid="column"] {
        min-width: 100% !important;
        flex: 1 1 100% !important;
    }

    /* Header compacto */
    .main-header {
        padding: 12px 16px !important;
        border-radius: 10px !important;
    }
    .main-header h1 {
        font-size: 18px !important;
        letter-spacing: 0 !important;
    }
    .main-header p { font-size: 12px !important; }

    /* Pomodoro menor */
    .pomodoro-display { font-size: 40px !important; }

    /* Tabs — texto menor */
    .stTabs [data-baseweb="tab"] {
        font-size: 11px !important;
        padding: 6px 8px !important;
    }

    /* Tabelas com scroll horizontal */
    [data-testid="stDataFrame"],
    [data-testid="stDataEditor"] {
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch !important;
    }

    /* Cards de métrica compactos */
    div[style*="border-radius:12px"] {
        padding: 12px 14px !important;
    }

    /* Botões full-width */
    .stButton > button {
        width: 100% !important;
    }

    /* Sidebar oculta por padrão — usuário abre manualmente */
    section[data-testid="stSidebar"] {
        transform: translateX(-100%) !important;
        position: fixed !important;
        z-index: 999 !important;
        height: 100vh !important;
        transition: transform 0.3s ease !important;
    }
    section[data-testid="stSidebar"][aria-expanded="true"] {
        transform: translateX(0) !important;
    }

    /* Conteúdo principal ocupa tela toda no mobile */
    .main .block-container {
        padding: 8px 10px !important;
        max-width: 100% !important;
    }

    /* Formulários: inputs full-width */
    .stTextInput input,
    .stSelectbox > div,
    .stNumberInput input {
        font-size: 14px !important;
    }

    /* Expanders mais compactos */
    [data-testid="stExpander"] {
        margin-bottom: 8px !important;
    }

    /* Sub-atividades: reduz recuo */
    .sub-activity {
        padding-left: 10px !important;
        margin-left: 8px !important;
    }
}
</style>
"""


def inject_css():
    """Injeta o CSS global no app Streamlit."""
    import streamlit as st
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "", icon: str = ""):
    """Renderiza o header padrão da página."""
    import streamlit as st
    st.markdown(f"""
    <div class="main-header">
        <h1>{icon} {title}</h1>
        {f'<p>{subtitle}</p>' if subtitle else ''}
    </div>
    """, unsafe_allow_html=True)
