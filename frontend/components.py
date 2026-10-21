from __future__ import annotations

import html
from urllib.parse import quote

import pandas as pd
import streamlit as st

from backend.transformations import brl, integer, percent


PALETTE = {
    "navy": "#0A3532",
    "blue": "#17534D",
    "cyan": "#21645D",
    "gold": "#C3A35F",
    "red": "#A63D40",
    "green": "#287A5A",
    "ink": "#17312E",
    "muted": "#60726E",
    "paper": "#F2F4F1",
}


NAV_ITEMS = (
    ("Visão Executiva", "Visão Executiva", "gauge"),
    ("Diagnóstico Atuarial", "Diagnóstico Atuarial", "chart"),
    ("Fluxos Atuariais", "Fluxos Atuariais", "trend"),
    ("Impacto Fiscal", "Impacto Fiscal", "landmark"),
)

# A demonstração pública mantém exatamente as quatro telas autorizadas.
# Módulos internos permanecem preservados fora da navegação e do pacote público.


NAV_ICONS = {
    "gauge": '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/><path d="M9 19h6"/>',
    "chart": '<path d="M3 3v18h18"/><path d="m7 16 4-5 3 3 5-7"/>',
    "trend": '<path d="M3 3v18h18"/><path d="m7 15 4-4 3 3 5-6"/><path d="M16 8h3v3"/>',
    "landmark": '<path d="m3 10 9-6 9 6"/><path d="M5 10v8"/><path d="M9 10v8"/><path d="M15 10v8"/><path d="M19 10v8"/><path d="M3 18h18"/><path d="M2 22h20"/>',
    "bars": '<path d="M4 20V10"/><path d="M10 20V4"/><path d="M16 20v-7"/><path d="M22 20H2"/>',
}


def render_navigation(selected: str) -> None:
    """Renderiza a navegação institucional com ícones SVG estáveis e estado por query param."""
    items = []
    for page, label, icon_key in NAV_ITEMS:
        active = page == selected
        current = ' aria-current="page"' if active else ""
        active_class = " is-active" if active else ""
        href = f"?page={quote(page)}"
        icon = NAV_ICONS[icon_key]
        items.append(
            # Explicitly bind the institutional route to the current browsing
            # context.  Streamlit reruns the same app from the query parameter;
            # no auxiliary tab/window is part of the navigation contract.
            f'<a class="institutional-nav__item{active_class}" href="{html.escape(href, quote=True)}"'
            f' target="_self" aria-label="{html.escape(label)}"{current}>'
            f'<svg class="institutional-nav__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
            f' stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{icon}</svg>'
            f'<span>{html.escape(label)}</span></a>'
        )
    st.sidebar.markdown(
        '<div class="institutional-nav" role="navigation" aria-label="Navegação principal">'
        '<div class="institutional-nav__label">Consulta atuarial</div>'
        + "".join(items)
        + "</div>",
        unsafe_allow_html=True,
    )


def inject_theme() -> None:
    st.markdown(
        """
        <style>
        :root { --deep:#0A3532; --green:#17534D; --gold:#C3A35F; --paper:#F2F4F1; --cream:#F7F4EB; --ink:#17312E; --muted:#60726E; }
        html, body, [class*="css"], .stApp { font-family:system-ui,-apple-system,"Segoe UI",Arial,sans-serif; color:var(--ink); }
        [data-testid="stAppViewContainer"] { background: var(--paper); }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stSidebar"] { background:linear-gradient(165deg,#0B3B37 0%,#0A312E 100%); min-width:274px; }
        [data-testid="stSidebar"] * { color:#F7F4EB; }
        .institutional-nav { padding-top:.6rem; display:flex; flex-direction:column; gap:.28rem; }
        .institutional-nav__label { padding:.55rem .72rem .45rem; color:rgba(247,244,235,.48); font-size:.66rem; font-weight:700; letter-spacing:.11em; text-transform:uppercase; }
        .institutional-nav__item { min-height:2.85rem; padding:.55rem .72rem; display:flex; align-items:center; gap:.72rem; border:1px solid transparent; border-radius:.72rem; color:rgba(247,244,235,.72); text-decoration:none; line-height:1.25; transition:background .16s ease,border-color .16s ease,color .16s ease; }
        .institutional-nav__item:hover, .institutional-nav__item:focus-visible { color:#fff; background:#17534D; border-color:rgba(195,163,95,.32); outline:none; }
        .institutional-nav__item.is-active { color:#173C38; background:linear-gradient(135deg,#D0B36F,#C3A35F); font-weight:700; box-shadow:0 7px 18px rgba(5,34,31,.18); }
        .institutional-nav__icon { width:1.08rem; height:1.08rem; flex:0 0 1.08rem; }
        .institutional-nav__item span { min-width:0; }
        .sidebar-divider { height:1px; margin:1rem 0 .8rem; background:rgba(247,244,235,.13); }
        [data-testid="stSidebar"] [data-testid="stRadio"] { display:none; }
        .block-container { max-width: 1440px; padding-top: 1.6rem; padding-bottom: 3rem; }
        h1, h2, h3 { color:var(--deep); font-family:Georgia,"Times New Roman",serif; letter-spacing:-.025em; }
        .brand-lockup { padding:.15rem 0 .7rem; border-bottom:1px solid rgba(247,244,235,.14); margin-bottom:.65rem; }
        .brand-name { font-family:Georgia,"Times New Roman",serif; color:#F7F4EB; font-size:1.35rem; font-weight:700; }
        .brand-name span { color:#D0B36F; font-family:system-ui,-apple-system,"Segoe UI",Arial,sans-serif; font-size:.78rem; font-weight:600; }
        .brand-kicker { color:#D0B36F; font-size:.63rem; letter-spacing:.16em; text-transform:uppercase; margin-top:.15rem; }
        .eyebrow { color:#17534D; font-size:.76rem; font-weight:700; letter-spacing:.14em; text-transform:uppercase; }
        .page-title { font-family:Georgia,"Times New Roman",serif; font-size:2.45rem; font-weight:700; color:var(--deep); margin:.12rem 0 .4rem; line-height:1.04; }
        .page-subtitle { color:var(--muted); font-size:1rem; max-width:880px; margin-bottom:1.35rem; }
        .metric-card { background:#fff; border:1px solid #DDE5E1; border-top:3px solid #C3A35F; border-radius:16px; padding:1.05rem 1.1rem; min-height:138px; box-shadow:0 8px 24px rgba(10,53,50,.06); }
        .metric-label { color:#60726E; text-transform:uppercase; font-size:.7rem; font-weight:700; letter-spacing:.08em; }
        .metric-value { color:#0A3532; font-family:Georgia,"Times New Roman",serif; font-size:1.68rem; font-weight:700; line-height:1.18; margin:.38rem 0; }
        .metric-detail { color:#60726E; font-size:.77rem; line-height:1.4; }
        .fiscal-projection-hero { margin:1rem 0 1.1rem; padding:1.2rem 1.25rem; border:1px solid #DDE5E1; border-radius:17px; background:linear-gradient(135deg,#173A35 0%,#0D3F3B 72%,#21645D 100%); color:#F7F4EB; box-shadow:0 12px 30px rgba(10,53,50,.12); }
        .fiscal-projection-hero__header { display:flex; align-items:flex-start; justify-content:space-between; gap:1rem; }
        .fiscal-projection-hero__eyebrow { color:#D0B36F; font-size:.68rem; font-weight:800; letter-spacing:.12em; text-transform:uppercase; }
        .fiscal-projection-hero__title { margin:.28rem 0 0; color:#F7F4EB; font-family:Georgia,"Times New Roman",serif; font-size:1.32rem; line-height:1.15; }
        .fiscal-projection-hero__year { color:#DDE8E4; font-size:.8rem; white-space:nowrap; }
        .fiscal-projection-hero__value { margin:.75rem 0 .2rem; color:#F7F4EB; font-family:Georgia,"Times New Roman",serif; font-size:clamp(2.25rem,5vw,3.5rem); font-weight:700; line-height:1; letter-spacing:-.035em; }
        .fiscal-projection-hero__detail { color:#DDE8E4; font-size:.78rem; line-height:1.45; }
        .fiscal-projection-hero__metrics { margin-top:1.1rem; display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.62rem; }
        .fiscal-projection-hero__metric { min-width:0; padding:.7rem .72rem; border:1px solid rgba(255,255,255,.14); border-radius:11px; background:rgba(255,255,255,.075); }
        .fiscal-projection-hero__metric span, .fiscal-projection-hero__metric strong { display:block; }
        .fiscal-projection-hero__metric span { color:#D0B36F; font-size:.61rem; font-weight:800; letter-spacing:.05em; text-transform:uppercase; }
        .fiscal-projection-hero__metric strong { margin-top:.3rem; color:#fff; font-size:.94rem; line-height:1.25; overflow-wrap:anywhere; }
        .fiscal-projection-chart { padding:1rem 1.05rem .75rem; border:1px solid #DDE5E1; border-radius:15px; background:#fff; }
        .fiscal-projection-chart__title { color:#173A35; font-family:Georgia,"Times New Roman",serif; font-size:1.06rem; font-weight:700; }
        .fiscal-projection-chart__subtitle { margin:.18rem 0 .75rem; color:#60726E; font-size:.76rem; line-height:1.45; }
        .fraction-card { background:#fff; border:1px solid #DDE5E1; border-top:4px solid #17534D; border-radius:16px; padding:1.1rem; min-height:320px; box-shadow:0 8px 24px rgba(10,53,50,.06); }
        .fraction-card--conditioned { border-top-color:#C3A35F; }
        .fraction-card__eyebrow { color:#8F743D; font-size:.69rem; font-weight:800; letter-spacing:.1em; text-transform:uppercase; }
        .fraction-card__title { color:#0A3532; font-family:Georgia,"Times New Roman",serif; font-size:1.36rem; font-weight:700; margin:.25rem 0 .85rem; }
        .fraction-card__row { display:flex; justify-content:space-between; align-items:flex-start; gap:1rem; padding:.48rem 0; border-top:1px solid #E7ECE9; }
        .fraction-card__row span { color:#60726E; font-size:.76rem; line-height:1.35; }
        .fraction-card__row strong { color:#17312E; font-size:.82rem; text-align:right; line-height:1.35; overflow-wrap:anywhere; }
        .fraction-card__status { margin-top:.8rem; padding:.48rem .58rem; border-radius:9px; background:#F7F1E3; color:#624A16; font-size:.72rem; font-weight:700; line-height:1.4; }
        .fraction-card__detail { color:#60726E; font-size:.72rem; line-height:1.45; margin-top:.65rem; }
        .fiscal-cost-table { width:100%; table-layout:fixed; border-collapse:separate; border-spacing:0; background:#fff; border:1px solid #DDE5E1; border-radius:13px; overflow:hidden; }
        .fiscal-cost-table th { padding:.72rem; background:#17534D; color:#fff; font-size:.7rem; text-align:left; text-transform:uppercase; letter-spacing:.04em; }
        .fiscal-cost-table td { padding:.72rem; border-top:1px solid #E7ECE9; color:#405652; font-size:.74rem; line-height:1.42; vertical-align:top; overflow-wrap:anywhere; }
        .fiscal-cost-table tr.is-total td { background:#F7F1E3; color:#17312E; font-weight:700; border-top:2px solid #C3A35F; }
        .fiscal-cost-table th:nth-child(1) { width:19%; } .fiscal-cost-table th:nth-child(2) { width:17%; }
        .fiscal-cost-table th:nth-child(3) { width:29%; } .fiscal-cost-table th:nth-child(4) { width:35%; }
        div[data-testid="stDialog"] div[role="dialog"] { width:min(1120px,calc(100vw - 2rem)); max-width:1120px; border-radius:18px; border:1px solid #D8E1DD; box-shadow:0 24px 70px rgba(3,28,25,.34); }
        div[data-testid="stDialog"] [data-testid="stVerticalBlock"] { gap:.7rem; }
        .manual-intro { color:#526762; font-size:.9rem; line-height:1.55; margin-bottom:.7rem; }
        .manual-section { margin:.7rem 0; padding:1rem; border:1px solid #DFE6E3; border-radius:12px; background:#fff; }
        .manual-section h3 { margin:0 0 .55rem; color:#0A3532; font-size:1.02rem; }
        .manual-section p, .manual-section li { color:#526762; font-size:.82rem; line-height:1.55; }
        .manual-formula { margin:.7rem 0; padding:.8rem 1rem; border-radius:10px; background:#173A35; color:#fff; text-align:center; font-family:system-ui,-apple-system,"Segoe UI",Arial,sans-serif; font-weight:700; }
        .manual-formula small { display:block; color:#DBC689; font-size:.66rem; letter-spacing:.08em; text-transform:uppercase; margin-bottom:.35rem; }
        .actuarial-metric { background:#fff; border:1px solid #DFE6E3; border-radius:17px; padding:1.2rem; min-height:156px; display:flex; gap:.95rem; align-items:flex-start; box-shadow:0 8px 24px rgba(10,53,50,.05); }
        .actuarial-metric--featured { background:linear-gradient(145deg,#0D3F3B,#17534D); border-color:#17534D; }
        .actuarial-metric__icon { width:42px; height:42px; flex:0 0 42px; display:grid; place-items:center; border-radius:12px; color:#8F743D; background:#F7F1E3; }
        .actuarial-metric__icon svg { width:21px; height:21px; }
        .actuarial-metric__content span { display:block; color:#71817D; font-size:.72rem; font-weight:700; letter-spacing:.035em; text-transform:uppercase; }
        .actuarial-metric__content strong { display:block; margin:.42rem 0 .3rem; color:#143D37; font-family:Georgia,"Times New Roman",serif; font-size:1.55rem; line-height:1.1; overflow-wrap:anywhere; }
        .actuarial-metric__content small { display:block; color:#71817D; font-size:.74rem; line-height:1.4; }
        .actuarial-metric--featured .actuarial-metric__content span, .actuarial-metric--featured .actuarial-metric__content small { color:#DDE8E4; }
        .actuarial-metric--featured .actuarial-metric__content strong { color:#F7F4EB; }
        .indicator-grid-marker { height:0; margin:0; padding:0; }
        .indicator-card { background:#F8FAF8; border:1px solid #E0E6E3; border-radius:13px; padding:1.05rem; min-height:218px; box-shadow:none; margin-bottom:.5rem; overflow:hidden; }
        .indicator-head { display:flex; justify-content:space-between; align-items:flex-start; gap:.7rem; }
        .indicator-code { color:#8F743D; font-size:1.02rem; font-weight:800; letter-spacing:.04em; }
        .indicator-status { color:#60726E; background:#E8EFEC; border-radius:999px; padding:.18rem .48rem; font-size:.62rem; font-weight:700; white-space:nowrap; }
        .indicator-name { color:#17312E; font-weight:700; line-height:1.3; min-height:2.5rem; margin:.35rem 0; overflow-wrap:anywhere; }
        .indicator-value { color:#143D37; font-family:Georgia,"Times New Roman",serif; font-size:1.58rem; font-weight:700; margin:.35rem 0; }
        .indicator-class { color:#17534D; font-size:.76rem; font-weight:700; margin-bottom:.55rem; }
        .indicator-copy { color:#60726E; font-size:.74rem; line-height:1.43; margin:.28rem 0; overflow-wrap:anywhere; }
        .indicator-copy strong { color:#405652; }
        .indicator-comparison { margin-top:.55rem; padding-top:.5rem; border-top:1px solid #E0E6E3; color:#516963; font-size:.72rem; }
        [data-testid="stExpander"] { border:1px solid #E0E6E3; border-radius:11px; background:#fff; }
        [data-testid="stExpander"] summary { color:#17534D; font-size:.78rem; font-weight:700; }
        div[role="radiogroup"] { gap:.35rem; flex-wrap:wrap; }
        div[role="radiogroup"] label { background:#E7ECE9; border:1px solid transparent; border-radius:999px; padding:.22rem .55rem; }
        .population-card { background:#fff; border:1px solid #DDE5E1; border-radius:16px; padding:1.05rem 1.1rem; min-height:174px; box-shadow:0 8px 24px rgba(10,53,50,.05); }
        .population-card .metric-value { margin-bottom:.7rem; }
        .payroll { border-top:1px solid #E7ECE9; padding-top:.62rem; color:#17312E; font-size:.88rem; font-weight:600; }
        .payroll small { display:block; color:#60726E; font-size:.7rem; font-weight:500; margin-top:.15rem; }
        .plan-meta { background:linear-gradient(120deg,#0D3F3B,#17534D); border-radius:16px; padding:1rem 1.1rem; color:#F7F4EB; margin:.25rem 0 1rem; }
        .plan-meta strong { color:#D0B36F; }
        .status-line { font-size:.77rem; margin-top:.42rem; color:#DDE8E4; }
        .pending-card { background:#F7F4EB; border:1px solid #E4D8BB; border-radius:14px; padding:1rem; min-height:145px; }
        .pending-card strong { color:#0A3532; }
        .pending-card .pending { color:#765515; font-size:.8rem; font-weight:700; margin:.45rem 0; }
        .notice { border-radius:12px; padding:.85rem 1rem; margin:.65rem 0 1rem; font-size:.9rem; }
        .notice-info { background:#E8F0ED; border-left:4px solid #21645D; color:#17312E; }
        .notice-warn { background:#F7F1E3; border-left:4px solid #C3A35F; color:#624A16; }
        .notice-risk { background:#FCEEEF; border-left:4px solid #A63D40; color:#6C2427; }
        .source-strip { color:#60726E; font-size:.74rem; padding:.45rem 0 .15rem; }
        .status-chip { display:inline-block; padding:.2rem .55rem; border-radius:999px; font-size:.72rem; font-weight:700; margin-right:.3rem; }
        .chip-ok { background:#E8F5EE; color:#1F6A4C; }
        .chip-note { background:#FFF3D6; color:#765515; }
        .chip-block { background:#FBE7E8; color:#8B3034; }
        [data-testid="stMetricValue"] { color:#0A3532; }
        [data-testid="stDataFrame"] { border:1px solid #E2E8F0; border-radius:10px; overflow:hidden; }
        [data-testid="stMultiSelect"] [data-baseweb="select"] > div { min-height:3rem; height:auto; align-items:flex-start; flex-wrap:wrap; row-gap:.25rem; }
        [data-testid="stMultiSelect"] [data-baseweb="tag"] { max-width:100%; height:auto; min-height:1.65rem; white-space:normal; }
        [data-testid="stMultiSelect"] [data-baseweb="tag"] span { max-width:100%; white-space:normal; overflow-wrap:anywhere; text-overflow:clip; }
        [data-testid="stMultiSelect"] input { min-width:1.25rem !important; }
        .stTabs [data-baseweb="tab-list"] { gap:.35rem; }
        .stTabs [data-baseweb="tab"] { background:#E7ECE9; border-radius:999px; padding:.35rem .85rem; }
        .stTabs [aria-selected="true"] { background:#17534D !important; color:#F7F4EB !important; }
        @media (max-width:980px) {
            [data-testid="stSidebar"] { min-width:88px; width:88px; }
            [data-testid="stSidebar"] .brand-name span, [data-testid="stSidebar"] .brand-kicker,
            [data-testid="stSidebar"] [data-testid="stCaptionContainer"] { display:none; }
            [data-testid="stSidebar"] .brand-name { font-size:.9rem; }
            .institutional-nav__label, .institutional-nav__item span { display:none; }
            .institutional-nav__item { justify-content:center; padding:.58rem .35rem; }
            .institutional-nav__icon { width:1.2rem; height:1.2rem; flex-basis:1.2rem; }
            .block-container { padding-left:1.15rem; padding-right:1.15rem; }
            .page-title { font-size:2rem; }
            [data-testid="stHorizontalBlock"] { flex-wrap:wrap !important; gap:.8rem !important; }
            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
                min-width:calc(50% - .4rem) !important; flex:1 1 calc(50% - .4rem) !important;
            }
        }
        @media (max-width:1050px) {
            .fiscal-projection-hero__metrics { grid-template-columns:repeat(2,minmax(0,1fr)); }
        }
        @media (max-width:700px) {
            [data-testid="stAppViewContainer"] { display:flex !important; flex-direction:column !important; }
            [data-testid="stSidebar"] {
                min-width:100% !important; width:100% !important; height:auto !important;
                min-height:0 !important; position:relative !important; inset:auto !important;
                transform:none !important; flex:0 0 auto !important;
            }
            [data-testid="stSidebar"] > div:first-child,
            [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
                width:100% !important; height:auto !important; position:relative !important;
                min-height:0 !important; padding-bottom:.75rem !important;
            }
            [data-testid="stSidebar"] [role="radiogroup"] {
                display:grid !important; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.2rem .45rem;
            }
            .institutional-nav { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.2rem .45rem; }
            .institutional-nav__label { grid-column:1 / -1; }
            .institutional-nav__item { min-height:2.7rem; justify-content:center; padding:.38rem .3rem; }
            .institutional-nav__item span { display:none; }
            [data-testid="stMain"], section.main {
                width:100% !important; margin-left:0 !important; margin-top:570px !important;
            }
            [data-testid="stSidebar"] .brand-name span, [data-testid="stSidebar"] .brand-kicker,
            [data-testid="stSidebar"] [data-testid="stCaptionContainer"], [data-testid="stSidebar"] label p { display:block; }
            .block-container { padding-top:1rem; padding-left:.85rem; padding-right:.85rem; }
            .page-title { font-size:1.72rem; }
            .metric-card, .population-card, .pending-card, .indicator-card { min-height:auto; }
            [data-testid="stDataFrame"] { font-size:.76rem; }
            [data-testid="stSelectbox"] label, [data-testid="stMultiSelect"] label { white-space:normal !important; }
            [data-testid="stMultiSelect"] [data-baseweb="tag"] { max-width:100%; }
            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
                min-width:100% !important; flex:1 1 100% !important;
            }
            .fiscal-cost-table, .fiscal-cost-table thead, .fiscal-cost-table tbody,
            .fiscal-cost-table tr, .fiscal-cost-table th, .fiscal-cost-table td { display:block; width:100% !important; }
            .fiscal-cost-table thead { position:absolute; left:-9999px; }
            .fiscal-cost-table { border:0; background:transparent; }
            .fiscal-cost-table tr { margin-bottom:.65rem; padding:.45rem; background:#fff; border:1px solid #DDE5E1; border-radius:12px; }
            .fiscal-cost-table td { display:grid; grid-template-columns:7.2rem minmax(0,1fr); gap:.55rem; padding:.48rem; border-top:1px solid #E7ECE9; }
            .fiscal-cost-table td:first-child { border-top:0; }
            .fiscal-cost-table td::before { content:attr(data-label); color:#60726E; font-size:.66rem; font-weight:700; text-transform:uppercase; }
            div[data-testid="stDialog"] div[role="dialog"] { width:calc(100vw - 1rem); max-height:calc(100vh - 1rem); }
            .manual-section { padding:.75rem; }
            .fiscal-projection-hero__header { flex-direction:column; gap:.3rem; }
            .fiscal-projection-hero__metrics { grid-template-columns:1fr; }
        }
        @media (max-width:480px) {
            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
                min-width:100% !important; flex:1 1 100% !important;
            }
            .indicator-head { flex-wrap:wrap; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str, eyebrow: str = "Painel Executivo") -> None:
    st.markdown(
        f'<div class="eyebrow">{html.escape(eyebrow)}</div>'
        f'<div class="page-title">{html.escape(title)}</div>'
        f'<div class="page-subtitle">{html.escape(subtitle)}</div>',
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, detail: str) -> None:
    st.markdown(
        '<div class="metric-card">'
        f'<div class="metric-label">{html.escape(label)}</div>'
        f'<div class="metric-value">{html.escape(value)}</div>'
        f'<div class="metric-detail">{html.escape(detail)}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def fiscal_fraction_card(
    title: str,
    subtitle: str,
    rows: list[tuple[str, str]],
    status: str,
    detail: str,
) -> None:
    """Renderiza uma fração executiva sem transformar ausência em zero."""
    content = "".join(
        '<div class="fraction-card__row">'
        f'<span>{html.escape(label)}</span><strong>{html.escape(value)}</strong>'
        "</div>"
        for label, value in rows
    )
    st.markdown(
        '<div class="fraction-card fraction-card--conditioned">'
        f'<div class="fraction-card__eyebrow">{html.escape(subtitle)}</div>'
        f'<div class="fraction-card__title">{html.escape(title)}</div>'
        f'{content}'
        f'<div class="fraction-card__status">{html.escape(status)}</div>'
        f'<div class="fraction-card__detail">{html.escape(detail)}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def fiscal_cost_table(frame: pd.DataFrame) -> None:
    """Tabela fiscal responsiva; em telas estreitas vira cartões sem rolagem horizontal."""
    headers = ["Componente", "Valor anual", "Critério de cálculo", "Fonte e situação"]
    head = "".join(f"<th>{html.escape(column)}</th>" for column in headers)
    rows = []
    for _, row in frame[headers].iterrows():
        cells = []
        for column in headers:
            value = row[column]
            if column == "Valor anual":
                value = brl(value) if pd.notna(value) else "N/A"
            elif pd.isna(value):
                value = "N/A"
            cells.append(
                f'<td data-label="{html.escape(column)}">{html.escape(str(value))}</td>'
            )
        component = str(row["Componente"])
        row_class = ' class="is-total"' if component.startswith("TOTAL") else ""
        rows.append(f"<tr{row_class}>" + "".join(cells) + "</tr>")
    st.markdown(
        '<table class="fiscal-cost-table"><thead><tr>'
        + head
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>",
        unsafe_allow_html=True,
    )


def fiscal_projection_summary(
    year: int,
    scenario: str,
    commitment: str,
    active_subtotal: str,
    insufficiency: str,
    total_with_insufficiency: str,
    rcl: str,
) -> None:
    """Destaca a projeção selecionada sem transformar a tela em uma planilha."""
    metrics = (
        ("Custo dos ativos conhecidos", active_subtotal),
        ("Insuficiência", insufficiency),
        ("Total com insuficiência", total_with_insufficiency),
        ("RCL ajustada", rcl),
    )
    metrics_html = "".join(
        '<div class="fiscal-projection-hero__metric">'
        f'<span>{html.escape(label)}</span><strong>{html.escape(value)}</strong>'
        "</div>"
        for label, value in metrics
    )
    st.markdown(
        '<section class="fiscal-projection-hero" aria-label="Resumo executivo da projeção">'
        '<div class="fiscal-projection-hero__header">'
        '<div><div class="fiscal-projection-hero__eyebrow">Comprometimento gerencial da RCL</div>'
        '<div class="fiscal-projection-hero__title">Pressão previdenciária condicionada</div></div>'
        f'<div class="fiscal-projection-hero__year">Cenário {html.escape(str(scenario))} · {int(year)}</div>'
        "</div>"
        f'<div class="fiscal-projection-hero__value">{html.escape(commitment)}</div>'
        '<div class="fiscal-projection-hero__detail">Sobre a RCL ajustada projetada; agregado gerencial condicionado e não equivalente à DTP oficial.</div>'
        f'<div class="fiscal-projection-hero__metrics">{metrics_html}</div>'
        "</section>",
        unsafe_allow_html=True,
    )
ACTUARIAL_ICONS = {
    "scale": '<path d="M12 3v18"/><path d="M5 7h14"/><path d="m5 7-3 6h6L5 7Z"/><path d="m19 7-3 6h6l-3-6Z"/><path d="M8 21h8"/>',
    "landmark": '<path d="m3 10 9-6 9 6"/><path d="M5 10v8"/><path d="M9 10v8"/><path d="M15 10v8"/><path d="M19 10v8"/><path d="M3 18h18"/>',
    "wallet": '<path d="M4 6h15a2 2 0 0 1 2 2v10H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h13"/><path d="M16 11h5"/>',
    "trend": '<path d="M3 3v18h18"/><path d="m7 15 4-4 3 3 5-6"/><path d="M16 8h3v3"/>',
}


def actuarial_metric_card(label: str, value: str, detail: str, icon: str, featured: bool = False) -> None:
    """Cartão da posição atuarial adaptado do padrão visual da ARIMA Intelligence."""
    icon_path = ACTUARIAL_ICONS.get(icon, ACTUARIAL_ICONS["trend"])
    css_class = "actuarial-metric actuarial-metric--featured" if featured else "actuarial-metric"
    st.markdown(
        f'<div class="{css_class}">'
        f'<div class="actuarial-metric__icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{icon_path}</svg></div>'
        '<div class="actuarial-metric__content">'
        f'<span>{html.escape(label)}</span><strong>{html.escape(value)}</strong><small>{html.escape(detail)}</small>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def indicator_card(
    code: str,
    name: str,
    value: str,
    classification: str,
    interpretation: str,
    comparison: str | None = None,
) -> None:
    """Cartão sintético; memória, fonte e limitações ficam no detalhamento recolhido."""
    comparison_html = (
        f'<div class="indicator-comparison">{html.escape(comparison)}</div>' if comparison else ""
    )
    st.markdown(
        '<div class="indicator-card">'
        '<div class="indicator-head">'
        f'<div class="indicator-code">{html.escape(code)}</div>'
        '<div class="indicator-status">2026 · PONTUAL</div>'
        '</div>'
        f'<div class="indicator-name">{html.escape(name)}</div>'
        f'<div class="indicator-value">{html.escape(value)}</div>'
        f'<div class="indicator-class">{html.escape(classification)}</div>'
        f'<div class="indicator-copy">{html.escape(interpretation)}</div>'
        f'{comparison_html}'
        '</div>',
        unsafe_allow_html=True,
    )


def population_card(label: str, quantity: str, payroll: str, detail: str) -> None:
    st.markdown(
        '<div class="population-card">'
        f'<div class="metric-label">{html.escape(label)}</div>'
        f'<div class="metric-value">{html.escape(quantity)}</div>'
        f'<div class="payroll">{html.escape(payroll)}<small>Folha mensal · {html.escape(detail)}</small></div>'
        "</div>",
        unsafe_allow_html=True,
    )


def plan_meta(plan: str, competence: str, status: str, reservation: str) -> None:
    st.markdown(
        '<div class="plan-meta">'
        f'<strong>{html.escape(plan)}</strong><br>{html.escape(competence)}'
        f'<div class="status-line">◉ {html.escape(status)} · {html.escape(reservation)}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def pending_rate_card(title: str) -> None:
    st.markdown(
        '<div class="pending-card">'
        f'<strong>{html.escape(title)}</strong>'
        '<div class="pending">◷ DEPENDENTE DE VALIDAÇÃO</div>'
        '<div class="metric-detail">Informação pendente de validação normativa. Lei, artigo, vigência e incidência não foram publicados neste estágio.</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def notice(text: str, kind: str = "info") -> None:
    css = {"info": "notice-info", "warn": "notice-warn", "risk": "notice-risk"}.get(kind, "notice-info")
    st.markdown(f'<div class="notice {css}">{html.escape(text)}</div>', unsafe_allow_html=True)


def source_strip(text: str) -> None:
    st.markdown(f'<div class="source-strip">Fonte e competência: {html.escape(text)}</div>', unsafe_allow_html=True)


def release_cards(frame: pd.DataFrame, columns: list[str], title_column: str = "Indicador") -> None:
    """Renderiza registros críticos em formato vertical, legível em telas estreitas."""
    for index, (_, row) in enumerate(frame[columns].iterrows()):
        title = str(row.get(title_column, f"Registro {index + 1}"))
        with st.container(border=True):
            st.markdown(f"**{html.escape(title)}**")
            for column in columns:
                if column == title_column:
                    continue
                value = row.get(column)
                if pd.isna(value):
                    value = "N/A"
                st.markdown(f"**{html.escape(column)}:** {html.escape(str(value))}")


def format_table(frame: pd.DataFrame, money: list[str] | None = None, pct: list[str] | None = None) -> pd.DataFrame:
    result = frame.copy()
    for column in money or []:
        if column in result:
            result[column] = result[column].map(lambda value: brl(value) if pd.notna(value) else "N/A")
    for column in pct or []:
        if column in result:
            result[column] = result[column].map(lambda value: percent(value) if pd.notna(value) else "N/A")
    return result


def compact_value(value: object, unit: str) -> str:
    if unit == "R$":
        return brl(value, compact=True)
    if unit == "%":
        return percent(value)
    return integer(value)

