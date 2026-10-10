"""Small presentation-only styles based on the supplied Overview reference."""

from urllib.parse import quote

import streamlit as st


def apply_overview_styles() -> None:
    """Style layout and workload cards without hiding errors or changing widgets."""
    icons = {
        "total": (
            "#E7F3FD", "#186197",
            '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v5h4M10 12h5M10 16h5"/>',
        ),
        "pending": (
            "#FFF2DC", "#A66A12",
            '<circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/>',
        ),
        "approved": (
            "#E0F4EE", "#207B68",
            '<path d="m6 12 4 4 8-9"/>',
        ),
        "denied": (
            "#FDE8EB", "#D94A5C",
            '<path d="m7 7 10 10M17 7 7 17"/>',
        ),
    }
    icon_rules = []
    for name, (background, foreground, paths) in icons.items():
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'fill="none" stroke="{foreground}" stroke-width="1.7" '
            f'stroke-linecap="round" stroke-linejoin="round">{paths}</svg>'
        )
        icon_rules.append(
            f'.st-key-card_{name} [data-testid="stMetricLabel"]::before {{'
            f'background-color: {background}; '
            f'background-image: url("data:image/svg+xml,{quote(svg)}"); }}'
        )
    css = """
    :root {
        --overview-font: "Source Sans Pro", sans-serif;
        --app-header-height: 90px;
    }
    html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"],
    h1, h2, h3, p, label, input, textarea, button, select,
    [data-baseweb="select"], [data-testid="stMetricValue"] {
        font-family: var(--overview-font) !important;
    }
    /* Keep the native header spacer, removing only the extra top inset. */
    .block-container { padding-top: 0 !important; padding-bottom: 2rem; }
    [data-testid="stSidebarUserContent"] { margin-top: -3rem; }
    /* The toolbar keeps its position, but its empty strip must not mask titles. */
    [data-testid="stHeader"] {
        background: transparent !important; pointer-events: none;
    }
    [data-testid="stToolbar"] { pointer-events: none; }
    [data-testid="stToolbarActions"],
    [data-testid="stToolbar"] button,
    [data-testid="stToolbar"] [role="button"],
    [data-testid="stToolbar"] a { pointer-events: auto; }
    h1, h2, h3 {
        font-size: 21px !important; font-weight: 700 !important;
        letter-spacing: -.02em; color: #0F766E !important; line-height: 1.4;
    }
    /* Reserve a separate top row for the title above both native columns. */
    [data-testid="stAppViewContainer"] {
        top: var(--app-header-height) !important;
        height: calc(100% - var(--app-header-height)) !important;
    }
    .st-key-application_header {
        position: fixed !important; top: 0; left: 0; right: 0;
        width: 100% !important; height: var(--app-header-height);
        min-height: var(--app-header-height); z-index: 999980;
        background: #FFFFFF; border-bottom: 1px solid #E2E7EE;
        display: flex; justify-content: center; align-items: center;
        padding: 0 2rem;
    }
    .st-key-application_header h1 {
        text-align: center; font-size: 30px !important;
        color: #17324D !important; line-height: 1.3;
        margin: 0; padding: 0 !important;
    }
    .st-key-workload_heading h2 {
        text-align: left; padding-top: 8px !important;
        padding-bottom: 32px !important;
    }
    @media (max-width: 767px) {
        :root { --app-header-height: 120px; }
        .st-key-application_header h1 { font-size: 26px !important; }
    }
    [data-testid="stWidgetLabel"] p, .overview-detail {
        font-size: 14px !important; font-weight: 400 !important;
        color: #17324D !important; line-height: 1.5;
    }
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
        font-size: .8125rem !important; font-weight: 400;
        color: #526279 !important; line-height: 1.5;
        opacity: 1 !important;
    }
    [data-testid="stSidebar"] { background: #F2F6FA; }
    /* Tighten sidebar grouping without shrinking labels, options, or controls. */
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: .55rem; }
    [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] > div {
        padding-top: .7rem !important; padding-bottom: .7rem !important;
    }
    .overview-nav {
        padding: .65rem .8rem; border-radius: 7px; background: #DCEFF0;
        color: #126B73; font-weight: 600; margin-bottom: 1rem;
    }
    .st-key-card_total, .st-key-card_pending,
    .st-key-card_approved, .st-key-card_denied {
        height: 190px; min-height: 190px; border-color: #E2E7EE !important;
        border-radius: 9px !important; background: #FFFFFF;
        box-shadow: 0 1px 3px rgba(15, 34, 63, .025);
    }
    [class*="st-key-card_"] [data-testid="stMetricLabel"] {
        display: flex; align-items: center; gap: .65rem;
        font-weight: 400; color: #17324D;
        grid-column: 1 / -1; grid-row: 1;
    }
    [class*="st-key-card_"] [data-testid="stMetric"] > div:first-child {
        display: grid; grid-template-columns: minmax(0, 1fr) auto;
        column-gap: 8px; row-gap: 8px; align-items: center;
    }
    [class*="st-key-card_"] [data-testid="stMetricValue"] {
        grid-column: 1; grid-row: 2;
    }
    [class*="st-key-card_"] [data-testid="stMetricValue"] + div {
        grid-column: 2; grid-row: 2; margin: 0;
        justify-self: end;
    }
    [class*="st-key-card_"] [data-testid="stMetricDelta"] {
        font-size: 14px; font-weight: 400; line-height: 1.4;
        border-radius: 0; padding: 0; white-space: nowrap;
        background: transparent !important;
    }
    .st-key-card_total [data-testid="stMetricDelta"] {
        color: #186197;
    }
    .st-key-card_pending [data-testid="stMetricDelta"] {
        color: #7A4B00;
    }
    .st-key-card_approved [data-testid="stMetricDelta"] {
        color: #0F766E;
    }
    .st-key-card_denied [data-testid="stMetricDelta"] {
        color: #A9273C;
    }
    .workload-share-track {
        height: 5px; width: 100%; background: #E8EDF2;
        border-radius: 3px; overflow: hidden;
    }
    .workload-share-fill { height: 100%; border-radius: 3px; }
    .st-key-card_total .workload-share-fill { background: #186197; }
    .st-key-card_pending .workload-share-fill { background: #A66A12; }
    .st-key-card_approved .workload-share-fill { background: #207B68; }
    .st-key-card_denied .workload-share-fill { background: #D94A5C; }
    [class*="st-key-card_"] [data-testid="stVerticalBlock"] { gap: .35rem; }
    [class*="st-key-card_"] [data-testid="stCaptionContainer"] p { margin-bottom: 0; }
    [class*="st-key-card_"] [data-testid="stMetricLabel"]::before {
        content: ""; flex: 0 0 32px; width: 32px; height: 32px;
        border-radius: 50%; background-size: 20px 20px;
        background-position: center; background-repeat: no-repeat;
    }
    [class*="st-key-card_"] [data-testid="stMetricValue"] {
        font-size: 2.5rem; line-height: 1.2; font-weight: 700; color: #17324D;
    }
    [class*="st-key-card_"] [data-testid="stCaptionContainer"] {
        color: #526279;
    }
    """
    st.markdown(
        "<style>" + css + "\n".join(icon_rules) + "</style>",
        unsafe_allow_html=True,
    )
