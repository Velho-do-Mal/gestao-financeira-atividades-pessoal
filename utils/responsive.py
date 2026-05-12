"""
utils/responsive.py
Detecção de viewport e utilitários de layout responsivo — BK Finance

Como funciona (v2 — não-bloqueante):
  - JS injeta a largura da janela via history.replaceState (sem reload/st.stop)
  - Na 1ª carga sem _vw, padrão = desktop; CSS media queries cuidam do visual
  - A partir da 2ª interação, Python também usa o breakpoint correto
  - O CSS é a garantia primária de responsividade — Python é complementar

Breakpoints:
  mobile:  ≤ 640 px   (celular)
  tablet:  641–1024 px (tablet, notebook pequeno)
  desktop: > 1024 px  (notebook, monitor)
"""

import streamlit as st
import streamlit.components.v1 as stcomp

_MOBILE_MAX = 640
_TABLET_MAX = 1024


# ══════════════════════════════════════════════════════════════════════════════
# DETECÇÃO DE VIEWPORT — NÃO BLOQUEANTE
# ══════════════════════════════════════════════════════════════════════════════

def init_responsive() -> str:
    """
    Chama no início de app.py.

    NÃO usa st.stop() — não causa tela em branco.

    Injeta JS que faz history.replaceState() com ?_vw=<px>.
    Na 1ª carga: _vw ausente → padrão desktop (CSS já cuida do layout visual).
    A partir da 2ª interação: Python lê _vw e usa o breakpoint real.

    Retorna: 'mobile' | 'tablet' | 'desktop'
    """
    # Injeta detector — height=0 = invisível, não bloqueia o render
    stcomp.html("""
    <script>
    (function () {
        try {
            var vw  = window.innerWidth;
            var url = new URL(window.parent.location.href);
            var cur = url.searchParams.get('_vw');
            // Só atualiza se mudou mais de 50px (evita loops desnecessários)
            if (!cur || Math.abs(parseInt(cur) - vw) > 50) {
                url.searchParams.set('_vw', String(vw));
                window.parent.history.replaceState({}, '', url.toString());
            }
        } catch (e) { /* CORS ou iframe — ignora silenciosamente */ }
    })();
    </script>
    """, height=0)

    # Lê o valor atual (pode ser vazio na 1ª carga — tudo bem)
    try:
        vw = int(st.query_params.get('_vw', 0))
    except (ValueError, TypeError):
        vw = 0

    # Fallback: usa valor anterior da sessão ou desktop
    if vw <= 0:
        vw = st.session_state.get('_vw', 1200)

    st.session_state['_vw']     = vw
    st.session_state['_device'] = _classify(vw)
    return st.session_state['_device']


def _classify(vw: int) -> str:
    if vw <= _MOBILE_MAX: return 'mobile'
    if vw <= _TABLET_MAX: return 'tablet'
    return 'desktop'


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DE CONSULTA
# ══════════════════════════════════════════════════════════════════════════════

def get_device() -> str:
    """Retorna 'mobile' | 'tablet' | 'desktop'. Padrão: desktop."""
    return st.session_state.get('_device', 'desktop')


def get_viewport_width() -> int:
    return st.session_state.get('_vw', 1200)


def is_mobile()  -> bool: return get_device() == 'mobile'
def is_tablet()  -> bool: return get_device() == 'tablet'
def is_desktop() -> bool: return get_device() == 'desktop'


def month_count() -> int:
    """Meses a exibir nas tabelas de fluxo. Menos = mais rápido em celular."""
    return {'mobile': 3, 'tablet': 6, 'desktop': 24}[get_device()]


# ══════════════════════════════════════════════════════════════════════════════
# COLUNAS RESPONSIVAS
# ══════════════════════════════════════════════════════════════════════════════

def rcols(mobile=1, tablet=None, desktop=None):
    """
    st.columns() com quantidade adaptada ao dispositivo.

    Exemplos:
        cols = rcols(1, 2, 4)   # mobile=1, tablet=2, desktop=4
        c1, c2 = rcols(1, 2, 2) # sempre ≥2 cols exceto no celular
    """
    if tablet  is None: tablet  = desktop if desktop is not None else mobile
    if desktop is None: desktop = tablet
    spec = {'mobile': mobile, 'tablet': tablet, 'desktop': desktop}[get_device()]
    return st.columns(spec)


def kpi_row(metrics: list):
    """
    Renderiza KPI cards responsivos.
    mobile=1/linha · tablet=2/linha · desktop=todos na mesma linha (máx 4)

    metrics: lista de dicts com keys: label, value, delta, color, icon
    """
    from utils.helpers import card_metric
    device = get_device()
    n_cols = {'mobile': 1, 'tablet': 2, 'desktop': min(len(metrics), 4)}[device]

    for row_start in range(0, len(metrics), n_cols):
        chunk = metrics[row_start: row_start + n_cols]
        cols  = st.columns(len(chunk))
        for col, m in zip(cols, chunk):
            with col:
                card_metric(
                    m.get('label', ''),
                    m.get('value', ''),
                    m.get('delta', ''),
                    m.get('color', '#60A5FA'),
                    m.get('icon',  '💰'),
                )
