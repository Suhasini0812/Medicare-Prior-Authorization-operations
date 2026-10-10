"""Shared snapshot/reporting context for Overview and Priority Review."""

from datetime import date

import pandas as pd
import streamlit as st

from src.filters import format_date, format_period, reporting_controls, reset_filters, table_controls
from src.metrics import get_received_date_range
from src.monthly_data import render_snapshot_review, render_upload_controls
from src.overview import render_request_table, render_summary
from src.priority_page import render_priority_review
from src.snapshot_store import SnapshotStore
from src.reporting import (
    ReportingPeriod, comparison_table, filter_period, filter_scope, filter_table, previous_period,
)


def render_overview(
    requests: pd.DataFrame, metadata: dict | None, source_key: str, store: SnapshotStore,
    *, screen: str = "Workload Overview",
) -> None:
    priority_review = screen == "Priority Review"
    overview = screen == "Workload Overview"
    if overview:
        render_upload_controls(store)
    if overview:
        st.subheader("Current Data Snapshot")
    current_view, volume = st.columns([3, 1])
    with current_view:
        if metadata is None:
            st.caption("Original supplied CSV")
            st.markdown(
                '<p class="overview-detail">Status snapshot date: Not recorded.</p>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<p class="overview-detail">Status snapshot date: '
                f"{format_date(date.fromisoformat(metadata['as_of']))}</p>",
                unsafe_allow_html=True,
            )
    with volume:
        st.markdown(
            f'<p class="overview-detail" style="text-align: right">Rows in snapshot: {len(requests):,}</p>',
            unsafe_allow_html=True,
        )
    if metadata is not None:
        render_snapshot_review(store, metadata["id"])

    date_range = get_received_date_range(requests)
    if date_range is None:
        st.error("No valid Received_Date values are available for reporting.")
        st.stop()
    coverage = (date_range[0].date(), date_range[1].date())
    available_period = ReportingPeriod("All available data", *coverage)
    st.markdown(
        f'<p class="overview-detail">Requests received (Received_Date): {format_period(available_period)}</p>',
        unsafe_allow_html=True,
    )
    if not priority_review and screen != "Ask the Data":
        st.caption(
            "Reporting periods use Received_Date. Displayed statuses come from the selected "
            "snapshot, not historical month-end status trends."
        )
    # Old ranges and categories may not exist in a different full snapshot.
    if st.session_state.get("last_overview_source") != source_key:
        reset_filters(coverage)
        st.session_state["last_overview_source"] = source_key
    with st.sidebar:
        period, categories, request_types = reporting_controls(requests, coverage)
    scoped = filter_scope(requests, categories, request_types)
    cohort = filter_period(scoped, period)
    if screen == "Ask the Data":
        # Lazy import: the existing screens do not load or construct an AI client.
        from src.ask_data_page import render_ask_data
        render_ask_data(
            cohort,
            snapshot_date="Not recorded" if metadata is None else format_date(date.fromisoformat(metadata["as_of"])),
            period_label=f"{period.mode} · {format_period(period)}",
            scope_key=(source_key, period.mode, period.start, period.end, tuple(categories), tuple(request_types)),
        )
    elif priority_review:
        render_priority_review(cohort)
    else:
        st.subheader("Workload at a Glance")
        render_summary(cohort)
    active_summary_filters = []
    if period.mode != "All available data":
        active_summary_filters.append(
            f"Reporting period: {period.mode} ({format_period(period)})"
        )
    if categories:
        active_summary_filters.append(f"Procedure category: {', '.join(categories)}")
    if request_types:
        active_summary_filters.append(f"Request type: {', '.join(request_types)}")
    if active_summary_filters:
        st.caption("Active summary filters · " + " · ".join(active_summary_filters))
    if period.start < coverage[0] or period.end > coverage[1]:
        st.warning(
            "The selected period extends beyond observed received-date coverage. "
            "Only available records are included; do not interpret this as a complete period."
        )
    compare = st.session_state.get("compare", False)
    with st.expander("About this data", expanded=False):
        snapshot_note = (
            "The date when these statuses were captured is unknown."
            if metadata is None else
            f"The status snapshot date was entered by the uploader: {format_date(date.fromisoformat(metadata['as_of']))}."
        )
        st.markdown(
            f"- {snapshot_note}\n"
            f"- Received-date coverage: {format_period(available_period)}.\n"
            "- Coverage does not prove this file is complete.\n"
            "- This single file does not show historical month-end statuses.\n"
            "- The denial rate is descriptive, not a quality score."
        )
    if compare:
        previous = previous_period(period)
        st.markdown("#### Received-cohort comparison")
        st.caption(
            f"Selected: {format_period(period)} · Previous: {format_period(previous)}. "
            "The same category and request-type filters apply to both. This compares "
            "received cohorts using recorded statuses in one snapshot, not status history."
        )
        st.dataframe(
            comparison_table(cohort, filter_period(scoped, previous)),
            hide_index=True, width="stretch",
        )
    if overview:
        st.divider()
        st.subheader("Prior Authorization Data")
        statuses, request_id = table_controls()
        render_request_table(filter_table(cohort, statuses, request_id), len(cohort))
