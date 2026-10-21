from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data_loader import DataLoadError, load_bundle  # noqa: E402
from backend.validators import validate_bundle  # noqa: E402
from frontend.components import inject_theme, notice, render_navigation  # noqa: E402
from frontend.views import (  # noqa: E402
    render_actuarial,
    render_executive,
    render_fiscal,
    render_flows,
)


st.set_page_config(
    page_title="Painel Executivo de Transição Previdenciária · MA",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_theme()

st.sidebar.markdown(
    '<div class="brand-lockup"><div class="brand-name">ARIMA <span>Intelligence</span></div>'
    '<div class="brand-kicker">Transição Previdenciária · Maranhão</div></div>',
    unsafe_allow_html=True,
)
PAGES = {
    "Visão Executiva": render_executive,
    "Diagnóstico Atuarial": render_actuarial,
    "Fluxos Atuariais": render_flows,
    "Impacto Fiscal": render_fiscal,
}


def resolve_public_page(requested_page: str | None) -> str:
    """Aceita somente as quatro rotas liberadas para a demonstração pública."""
    return requested_page if requested_page in PAGES else "Visão Executiva"


requested_page = resolve_public_page(st.query_params.get("page", "Visão Executiva"))
page_names = list(PAGES)
default_index = page_names.index(requested_page)
# Mantém o contrato de testes do Streamlit sem expor o marcador circular como navegação primária.
selection = st.sidebar.radio("Navegação", page_names, index=default_index, label_visibility="collapsed")
render_navigation(selection)
st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
st.sidebar.caption("Demonstração pública · acesso sem login")
st.sidebar.caption("Bases públicas · atualização 13/10/2026")

try:
    bundle = load_bundle()
    issues = validate_bundle(bundle)
    errors = [issue for issue in issues if issue.severity == "erro"]
    if errors:
        for issue in errors:
            notice(f"{issue.code}: {issue.message}", "risk")
        st.stop()
    PAGES[selection](bundle)
except DataLoadError:
    notice("Os dados públicos não puderam ser carregados neste momento.", "risk")
    st.info("Tente novamente mais tarde.")
except Exception:  # pragma: no cover - proteção de interface
    notice("A página não pôde ser exibida neste momento.", "risk")
    st.info("Tente novamente mais tarde.")

