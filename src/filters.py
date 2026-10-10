"""Streamlit controls for the reporting scope and request list filters."""

from datetime import date

import pandas as pd
import streamlit as st

from src.reporting import (
    ReportingPeriod, STATUSES, calendar_period, comparison_availability, filter_scope,
)


def reset_filters(coverage: tuple[date, date]) -> None:
    """Set explicit values so the browser and Python reset the same widgets."""
    st.session_state.update({
        "period_mode": "All available data",
        "month": str(pd.Period(coverage[1], freq="M")),
        "quarter": str(pd.Period(coverage[1], freq="Q")),
        "year": coverage[1].year,
        "start_date": coverage[0],
        "end_date": coverage[1],
        "categories": [],
        "request_types": [],
        "table_statuses": [],
        "request_id": "",
        "compare": False,
        "request_page": 1,
        "saved_table_statuses": [],
        "saved_request_id": "",
        "saved_request_page": 1,
    })


def remember_request_list_value(key: str) -> None:
    """Keep a non-widget copy that survives visiting another screen."""
    st.session_state[f"saved_{key}"] = st.session_state[key]


def restore_request_list_value(key: str, default) -> None:
    """Restore an absent widget before creation so the browser receives its value."""
    if key not in st.session_state:
        st.session_state[key] = st.session_state.get(f"saved_{key}", default)


def format_date(value: date) -> str:
    return f"{value:%B} {value.day}, {value.year}"


def format_period(period: ReportingPeriod) -> str:
    return f"{format_date(period.start)} – {format_date(period.end)}"


def reporting_controls(
    requests: pd.DataFrame, coverage: tuple[date, date],
) -> tuple[ReportingPeriod, list[str], list[str]]:
    with st.container(border=True):
        st.markdown("#### Reporting scope")
        st.button(
            "Reset all filters", on_click=reset_filters, args=(coverage,),
            width="stretch",
        )
        mode = st.radio(
            "Received-date reporting period",
            ["All available data", "Month", "Quarter", "Year", "Custom"],
            key="period_mode",
        )
        if mode == "Month":
            months = pd.period_range(coverage[0], coverage[1], freq="M")
            month = st.selectbox(
                "Month", [str(p) for p in months], index=len(months) - 1,
                format_func=lambda value: pd.Period(value, freq="M").strftime("%B %Y"),
                key="month",
            )
            period = calendar_period(mode, month)
        elif mode == "Quarter":
            quarters = pd.period_range(coverage[0], coverage[1], freq="Q")
            quarter = st.selectbox(
                "Quarter", [str(p) for p in quarters], index=len(quarters) - 1,
                format_func=lambda value: f"Q{value[-1]} {value[:4]}",
                key="quarter",
            )
            period = calendar_period(mode, quarter)
        elif mode == "Year":
            year = st.selectbox(
                "Year", list(range(coverage[0].year, coverage[1].year + 1)),
                index=coverage[1].year - coverage[0].year, key="year",
            )
            period = calendar_period(mode, str(year))
        elif mode == "Custom":
            start = st.date_input(
                "Start date", value=coverage[0], key="start_date"
            )
            end = st.date_input(
                "End date", value=coverage[1], key="end_date"
            )
            if start > end:
                st.error("Start date must be on or before end date.")
                st.stop()
            period = ReportingPeriod(mode, start, end)
        else:
            period = ReportingPeriod(mode, *coverage)
        # Reserve a place beside the period controls, then evaluate availability
        # after reading the category and request-type selections below.
        comparison_slot = st.container()
        categories = st.multiselect(
            "Procedure category",
            sorted(requests["Procedure_Category"].dropna().unique()),
            key="categories", placeholder="All procedure categories",
        )
        request_types = st.multiselect(
            "Request type", sorted(requests["Request_Type"].dropna().unique()),
            key="request_types", placeholder="All request types",
        )
        supported, _ = comparison_availability(
            filter_scope(requests, categories, request_types), period, coverage
        )
        with comparison_slot:
            if not supported:
                st.session_state["compare"] = False
            if mode == "All available data":
                st.session_state["compare"] = False
            elif supported:
                labels = {
                    "Month": "Compare with previous month",
                    "Quarter": "Compare with previous quarter",
                    "Year": "Compare with previous year",
                    "Custom": "Compare with the previous period of the same length.",
                }
                st.checkbox(labels[mode], key="compare")
            else:
                st.caption(
                    "A previous-period comparison is unavailable for this reporting scope."
                )
    return period, categories, request_types


def table_controls() -> tuple[list[str], str]:
    restore_request_list_value("table_statuses", [])
    restore_request_list_value("request_id", "")
    st.caption(
        "These controls narrow the request list below; they do not change the summary cards."
    )
    status_column, search_column = st.columns(2)
    statuses = status_column.multiselect(
        "Status", STATUSES, key="table_statuses",
        placeholder="All statuses",
        on_change=remember_request_list_value, args=("table_statuses",),
    )
    request_id = search_column.text_input(
        "PA Request ID search", key="request_id",
        placeholder="Enter all or part of an ID",
        on_change=remember_request_list_value, args=("request_id",),
    )
    return statuses, request_id
