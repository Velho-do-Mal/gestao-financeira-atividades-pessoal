"""
utils/responsive.py
Detecção de viewport e utilitários de layout responsivo — BK Finance

Como funciona:
  1ª carga sem '_vw' na URL: JS detecta window.innerWidth e faz replace()
  para a mesma URL com ?_vw=<px>. É um único redirect invisível ao usuário.
  Cargas seguintes: lê _vw de st.query_params, sem overhead adicional.

Breakpoints:
  mobile:  ≤ 640 px   (celular)
  tablet:  641–1024 px (tablet, notebook pequeno)
  desktop: > 1024 px  (notebook, monitor)

Uso básico:
    # app.py — chamar antes de qualquer render
    from utils.responsive import init_responsive
    init_responsive()

    # qualquer página
    from utils.responsive import rcols, is_mobile, month_count

    cols = rcols(1, 2, 4)          # mobile=1col, tablet=2col, desktop=4col
    with cols[0]: ...
    with cols[min(1, len(cols)-1)]: ...
"""

import streamlit as st
import streamlit.components.v1 as stcomp

_MOBILE_MAX = 640
_TABLET_MAX = 1024


# ══════════════════════════════════════════════════════════════════════════════
# DETECÇÃO DE VIEWPORT
# ══════════════════════════════════════════════════════════════════════════════

def init_responsive() -> str:
    """
    Deve ser chamado no início de app.py, logo após inject_css().

    Na primeira carga (sem _vw na URL), injeta um script JS que:
      1. Lê window.innerWidth
      2. Faz window.parent.location.replace() adicionando ?_vw=<px>
      3. st.stop() segura o render até o redirect acontecer

    Nas cargas seguintes, apenas lê st.query_params['_vw'] e retorna o device.

    Retorna: 'mobile' | 'tablet' | 'desktop'
    """
    if '_vw' not in st.query_params:
        # Injetar detector — height=0 torna invisível
        stcomp.html("""
        <script>
            (function () {
                var vw  = window.innerWidth;
                var url = new URL(window.parent.location.href);
                url.searchParams.set('_vw', String(vw));
                window.parent.location.replace(url.toString());
            })();
        </script>
        """, height=0)
        st.stop()  # Aguarda o redirect antes de continuar o render

    try:
        vw = int(st.query_params.get('_vw', 1200))
    except (ValueError, TypeError):
        vw = 1200

    st.session_state['_vw']     = vw
    st.session_state['_device'] = _classify(vw)
    return st.session_state['_device']


def _classify(vw: int) -> str:
    if vw <= _MOBILE_MAX:
        return 'mobile'
    if vw <= _TABLET_MAX:
        return 'tablet'
    return 'desktop'


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DE CONSULTA
# ══════════════════════════════════════════════════════════════════════════════

def get_device() -> str:
    """Retorna 'mobile' | 'tablet' | 'desktop' (sem re-injetar JS)."""
    return st.session_state.get('_device', 'desktop')


def get_viewport_width() -> int:
    """Retorna largura do viewport em pixels."""
    return st.session_state.get('_vw', 1200)


def is_mobile() -> bool:
    return get_device() == 'mobile'


def is_tablet() -> bool:
    return get_device() == 'tablet'


def is_desktop() -> bool:
    return get_device() == 'desktop'


def month_count() -> int:
    """
    Número de meses a exibir nas tabelas de fluxo de caixa.
    Reduz em telas pequenas para não travar a renderização.
    """
    return {'mobile': 3, 'tablet': 6, 'desktop': 24}[get_device()]


# ══════════════════════════════════════════════════════════════════════════════
# COLUNAS RESPONSIVAS
# ══════════════════════════════════════════════════════════════════════════════

def rcols(mobile=1, tablet=None, desktop=None):
    """
    Retorna st.columns() com quantidade adaptada ao dispositivo.

    Parâmetros:
        mobile   — int ou lista de pesos para celular
        tablet   — int ou lista de pesos para tablet (herda mobile se omitido)
        desktop  — int ou lista de pesos para desktop (herda tablet se omitido)

    Exemplos:
        # KPIs: 1 col celular / 2 tablet / 4 desktop
        cols = rcols(1, 2, 4)

        # Formulário 2 campos: sempre 1 no celular, 2 no resto
        c1, c2 = rcols(1, 2, 2)  # só funciona se tablet+desktop retornam >=2

        # Com pesos: sidebar de gráfico
        cols = rcols(1, [3, 2], [3, 2])

    ATENÇÃO ao desempacotar:
        Para layouts onde o número muda, prefira acesso por índice:
            cols = rcols(1, 2, 4)
            with cols[0]: ...
            with cols[min(1, len(cols)-1)]: ...
    """
    if tablet  is None: tablet  = desktop if desktop is not None else mobile
    if desktop is None: desktop = tablet

    spec = {'mobile': mobile, 'tablet': tablet, 'desktop': desktop}[get_device()]
    return st.columns(spec)


def kpi_row(metrics: list):
    """
    Renderiza uma linha de cards de KPI de forma responsiva.

    metrics: lista de dicts com keys: label, value, delta, color, icon
    Em mobile: empilha 1 por linha.
    Em tablet: 2 por linha.
    Em desktop: todos na mesma linha (máx 4).

    Exemplo:
        kpi_row([
            dict(label="Receita", value="R$ 10.000", delta="", color="#10B981", icon="📥"),
            dict(label="Despesa", value="R$ 8.000",  delta="", color="#EF4444", icon="📤"),
        ])
    """
    from utils.helpers import card_metric

    device = get_device()
    n_cols = {'mobile': 1, 'tablet': 2, 'desktop': min(len(metrics), 4)}[device]

    # Divide em linhas
    for row_start in range(0, len(metrics), n_cols):
        chunk = metrics[row_start : row_start + n_cols]
        cols  = st.columns(len(chunk))
        for col, m in zip(cols, chunk):
            with col:
                card_metric(
                    m.get('label', ''),
                    m.get('value', ''),
                    m.get('delta', ''),
                    m.get('color', '#60A5FA'),
                    m.get('icon', '💰'),
                )
