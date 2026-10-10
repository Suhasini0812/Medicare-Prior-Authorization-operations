"""Priority Review: two separate category-level investigation signals."""

import pandas as pd
import streamlit as st

from src.priority_metrics import category_summary, highest_pending_rate, largest_pending_workload
from src.priority_charts import render_category_charts


def _lines(rows: pd.DataFrame, with_rate: bool) -> None:
    for row in rows.itertuples(index=False):
        text = (
            f"**{row.Procedure_Category}**: {int(row.Pending):,} Pending "
            f"of {int(row.Total_Requests):,} total requests"
        )
        if with_rate:
            text += f" ({float(row.Pending_Rate):.1f}%)"
        st.markdown("- " + text)


def render_priority_review(requests: pd.DataFrame) -> None:
    summary = category_summary(requests)
    if summary.empty:
        st.warning(
            "No requests match the current selection, so no priority signals are shown. "
            "Adjust the reporting period or filters."
        )

    workload = largest_pending_workload(summary)
    rate = highest_pending_rate(summary)
    no_pending = not summary.empty and int(summary["Pending"].sum()) == 0
    if no_pending:
        st.info(
            "No Pending requests are recorded in this reporting scope. "
            "The zero-Pending ties below are not priority leads."
        )
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.subheader("Largest Pending Workload")
            if workload.empty:
                st.markdown("No requests in this reporting scope.")
            else:
                if len(workload) > 1:
                    st.markdown(f"**Tie: {len(workload)} categories share the largest Pending count.**")
                _lines(workload, with_rate=False)
            st.caption(
                "Compares the volume of unresolved requests: the category with the most "
                "Pending requests to review."
            )
    with right:
        with st.container(border=True):
            st.subheader("Highest Pending Rate")
            if rate.empty:
                st.markdown("No requests in this reporting scope.")
            else:
                if len(rate) > 1:
                    st.markdown(f"**Tie: {len(rate)} categories share the highest Pending rate.**")
                _lines(rate, with_rate=True)
            st.caption(
                "Compares share of workload: Pending requests divided by category total. "
                "A high rate in a low-volume category should be interpreted cautiously."
            )
    st.caption("These are two separate signals and are not combined into a score.")

    render_category_charts(summary)

    st.subheader("Category Summary")
    st.dataframe(
        summary, hide_index=True, width="stretch",
        column_config={
            "Procedure_Category": "Procedure_Category",
            "Total_Requests": st.column_config.NumberColumn("Total requests", format="%d"),
            "Pending": st.column_config.NumberColumn("Pending", format="%d"),
            "Pending_Rate": st.column_config.NumberColumn("Pending rate", format="%.1f%%"),
            "Approved": st.column_config.NumberColumn("Approved", format="%d"),
            "Denied": st.column_config.NumberColumn("Denied", format="%d"),
        },
    )
    st.caption("Sorted by Pending count, highest first. Rates use all requests in each category.")

