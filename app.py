"""Portable Streamlit entry point for the combined Workload Overview."""

import sqlite3

import streamlit as st

from src.overview_page import render_overview
from src.snapshot_selection import ORIGINAL_OPTION, load_selected_snapshot, snapshot_options
from src.snapshot_store import SnapshotStore
from src.styles import apply_overview_styles


st.set_page_config(page_title="Prior Authorization Operations", layout="wide")
apply_overview_styles()
with st.container(key="application_header"):
    st.title("Prior Authorization Operations Dashboard", anchor=False)
st.sidebar.markdown("### PA Operations")
screen = st.sidebar.radio(
    "Navigation", ["Workload Overview", "Priority Review", "Ask the Data"], key="screen",
)
with st.container(key="workload_heading"):
    st.header(
        "Prior Authorization Workload Review"
        if screen == "Workload Overview" else
        ("Priority Review - Current Data Snapshot" if screen == "Priority Review" else
         "Ask the Data - Current Data Snapshot")
    )

try:
    store = SnapshotStore()
    snapshots = store.list_snapshots()
    options = snapshot_options(snapshots)
    metadata_by_option = {f"snapshot:{item['id']}": item for item in snapshots}

    def option_label(option: str) -> str:
        if option == ORIGINAL_OPTION:
            return "Status snapshot date: Not recorded. · Original CSV"
        item = metadata_by_option[option]
        newest = " · Newest saved" if option == options[0] else ""
        return (
            f"{item['as_of']} · Revision {item['revision']}{newest} · {item['filename']}"
        )
    requested = st.session_state.pop("requested_snapshot", None)
    if requested in options:
        st.session_state["selected_snapshot"] = requested
    if st.session_state.get("selected_snapshot") not in options:
        st.session_state["selected_snapshot"] = options[0]
    selected = st.sidebar.selectbox(
        "Snapshot to view", options, format_func=option_label, key="selected_snapshot",
        help="Choose one status snapshot. Received-date reporting periods filter its requests, not snapshot history.",
    )
    st.sidebar.caption(
        "Original supplied CSV"
        if selected == ORIGINAL_OPTION else
        "Snapshot dates are status as-of dates, not request received dates."
    )
    requests, metadata = load_selected_snapshot(store, selected)
    render_overview(requests, metadata, selected, store, screen=screen)
except (OSError, ValueError, sqlite3.Error) as error:
    st.error(f"Could not load the selected data: {error}")
    st.stop()
