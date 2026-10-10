"""Readable summary cards and a horizontally scrollable request table."""

import pandas as pd
import streamlit as st

from src.filters import remember_request_list_value, restore_request_list_value
from src.reporting import status_summary
from src.pagination import paginate_requests


def _move_page(offset: int) -> None:
    st.session_state["request_page"] += offset
    remember_request_list_value("request_page")


def _render_share_bar(label: str, percentage: float | None) -> None:
    """Show the same summary share as a slim bar, without adding data logic."""
    fill = percentage if percentage is not None else 0
    description = f"{label} share" if percentage is not None else f"{label}: no selected requests"
    st.markdown(
        f'<div class="workload-share-track" role="meter" aria-label="{description}" '
        f'aria-valuemin="0" aria-valuemax="100" aria-valuenow="{fill:.6f}">'
        f'<div class="workload-share-fill" style="width:{fill:.6f}%"></div></div>',
        unsafe_allow_html=True,
    )


def render_summary(requests: pd.DataFrame) -> None:
    summary = status_summary(requests)
    total = summary["total"]
    columns = st.columns(4)
    with columns[0].container(border=True, key="card_total"):
        st.metric("Total Requests", f"{total:,}", delta="100%",
                  delta_color="off", delta_arrow="off")
        _render_share_bar("Total Requests", 100)
    for column, status in zip(columns[1:], ("Pending", "Approved", "Denied")):
        with column.container(border=True, key=f"card_{status.lower()}"):
            percentage = summary["percentages"][status]
            share = f"{percentage:.1f}%" if percentage is not None else "Not available"
            st.metric(status, f"{summary['counts'][status]:,}", delta=share,
                      delta_color="off", delta_arrow="off")
            _render_share_bar(status, percentage)
    if total != sum(summary["counts"].values()):
        st.warning("Some selected requests have other or missing statuses; they remain in the denominator.")


def render_request_table(requests: pd.DataFrame, cohort_total: int) -> None:
    if requests.empty:
        st.info("No requests match these filters. Adjust the selections or reset all filters.")
    restore_request_list_value("request_page_size", 25)
    restore_request_list_value("request_page", 1)
    # Widgets below the table commit values before the next script run.
    size = st.session_state.get("request_page_size", 25)
    # A new matching list or page size must not leave the user on a stale page.
    signature = (size, tuple(requests["PA_Request_ID"].astype(str)))
    if st.session_state.get("request_list_signature") != signature:
        st.session_state["request_page"] = 1
        st.session_state["request_list_signature"] = signature
    page = paginate_requests(requests, st.session_state.get("request_page", 1), size)
    st.session_state["request_page"] = page.number
    remember_request_list_value("request_page")
    st.caption("All ten columns are included. Scroll horizontally inside the table to see the remaining columns.")
    column_config = {
        name: st.column_config.Column(
            name, width="large" if name in ("Procedure_Category", "Denial_Reason") else "medium"
        )
        for name in requests.columns
    }
    st.dataframe(
        page.rows, hide_index=True, width="stretch", height=460,
        column_config=column_config,
    )
    st.caption(
        f"Showing rows {page.first:,}–{page.last:,} of {len(requests):,} matching records "
        f"· Page {page.number:,} of {page.pages:,}"
    )
    size_column, page_column = st.columns(2)
    size_column.selectbox(
        "Rows per page", [25, 50, 100], key="request_page_size",
        on_change=remember_request_list_value, args=("request_page_size",),
    )
    page_column.number_input(
        "Page", min_value=1, max_value=page.pages, step=1, key="request_page",
        disabled=page.pages == 1,
        on_change=remember_request_list_value, args=("request_page",),
    )
    previous, following = st.columns(2)
    previous.button(
        "Previous page", key="previous_page", disabled=page.number == 1,
        on_click=_move_page, args=(-1,),
    )
    following.button(
        "Next page", key="next_page", disabled=page.number == page.pages,
        on_click=_move_page, args=(1,),
    )
