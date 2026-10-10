"""Compact charts of the existing category summary, without new calculations."""

import altair as alt
import pandas as pd
import streamlit as st


def build_category_chart(summary: pd.DataFrame, *, rate: bool = False) -> alt.Chart:
    """Rank each metric independently; convert rates only for percent formatting."""
    metric = "Pending_Rate" if rate else "Pending"
    data = summary.sort_values(
        [metric, "Procedure_Category"], ascending=[False, True], kind="stable",
    ).reset_index(drop=True).copy()
    data["Pending_Share"] = data["Pending_Rate"] / 100
    value = "Pending_Share" if rate else "Pending"
    axis = alt.Axis(format=".1%", tickCount=4) if rate else alt.Axis(
        format=",.0f", tickMinStep=1, tickCount=4,
    )
    return (
        alt.Chart(data)
        .mark_bar(color="#0F766E" if rate else "#1E648A", size=18, cornerRadiusEnd=3)
        .encode(
            y=alt.Y(
                "Procedure_Category:N", title=None,
                sort=data["Procedure_Category"].tolist(),
                axis=alt.Axis(labelLimit=190),
            ),
            x=alt.X(
                f"{value}:Q", title="Pending rate" if rate else "Pending requests",
                axis=axis, scale=alt.Scale(zero=True),
            ),
            tooltip=[
                alt.Tooltip("Procedure_Category:N", title="Category"),
                alt.Tooltip("Pending:Q", title="Pending requests", format=",.0f"),
                alt.Tooltip("Total_Requests:Q", title="Category total", format=",.0f"),
                alt.Tooltip("Pending_Share:Q", title="Pending rate", format=".1%"),
            ],
        )
        # Streamlit fits axes inside this frame, so reserve room for them as well
        # as separate category rows; otherwise bars and labels can overlap.
        .properties(height=max(160, len(data) * 32 + 72))
        .configure(font="Source Sans Pro")
        .configure_axis(
            labelColor="#17324D", titleColor="#17324D",
            labelFontSize=12, titleFontSize=12, grid=False,
        )
        .configure_view(stroke=None)
    )


def render_category_charts(summary: pd.DataFrame) -> None:
    """Native Streamlit columns wrap on narrow screens; chart widths follow them."""
    count_column, rate_column = st.columns(2)
    for column, rate, title, key in (
        (count_column, False, "Pending Requests by Category", "priority_pending_count_chart"),
        (rate_column, True, "Pending Rate by Category", "priority_pending_rate_chart"),
    ):
        with column:
            st.subheader(title)
            if summary.empty:
                st.caption("No requests in this reporting scope.")
            else:
                st.altair_chart(
                    build_category_chart(summary, rate=rate), width="stretch", key=key,
                    alt=f"{title}. Horizontal bars, ordered highest to lowest.",
                )
