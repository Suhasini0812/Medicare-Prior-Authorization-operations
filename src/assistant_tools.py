"""Allowlisted aggregate tools. Data stays in Python, outside model messages."""

from typing import Literal

import pandas as pd
from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict

from src.priority_metrics import category_summary, highest_pending_rate, largest_pending_workload
from src.reporting import status_summary


class NoArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CategoryArguments(NoArguments):
    view: Literal["summary", "largest_pending_count", "highest_pending_rate", "largest_request_total"]
    category: str | None = None


class LimitationArguments(NoArguments):
    reason: Literal["unavailable_calculation", "outside_scope", "unsafe_request"]


LIMITATIONS = {
    "unavailable_calculation": (
        "I can explain recorded status totals and category request totals, Pending counts, "
        "and Pending rates. The available tools cannot answer this question."
    ),
    "outside_scope": (
        "Answers use only the selected snapshot and received-date reporting period. "
        "Change the sidebar selections to review another scope. One snapshot does not "
        "show historical month-end statuses or explain changes between snapshots."
    ),
    "unsafe_request": (
        "This screen does not explain causes, provide clinical guidance or individual "
        "approval/denial recommendations, rank employees, or look up individual requests."
    ),
}


def make_tools(cohort: pd.DataFrame) -> dict:
    """Create two calculation tools and one fixed limitation response."""
    @tool(args_schema=NoArguments)
    def status_totals() -> dict:
        """Get recorded Total, Pending, Approved, Denied counts and percentages in current scope."""
        summary = status_summary(cohort)
        total = summary["total"]
        rows = [{"Status": "Total Requests", "Count": total, "Denominator": total,
                 "Rate": 100.0 if total else 0.0}]
        rows.extend(
            {"Status": status, "Count": summary["counts"][status],
             "Denominator": total, "Rate": summary["percentages"][status]}
            for status in ("Pending", "Approved", "Denied")
        )
        return {"kind": "status_totals", "rows": rows}

    @tool(args_schema=CategoryArguments)
    def category_pending(view: str, category: str | None = None) -> dict:
        """Get category request totals, Pending counts/rates, or exact count/rate leaders.

        Use summary for category comparisons, including Approved/Denied counts.
        category optionally restricts results to an exact category name (case-insensitive).
        Count leaders and rate leaders are different signals; ties are retained.
        """
        summary = category_summary(cohort)
        if category is not None:
            summary = summary.loc[
                summary["Procedure_Category"].astype(str).str.casefold().eq(category.strip().casefold())
            ]
        if view == "largest_pending_count":
            summary = largest_pending_workload(summary)
        elif view == "highest_pending_rate":
            summary = highest_pending_rate(summary)
        elif view == "largest_request_total" and not summary.empty:
            summary = summary.loc[summary["Total_Requests"].eq(summary["Total_Requests"].max())]
        rows = [
            {"Category": str(row.Procedure_Category), "Total requests": int(row.Total_Requests),
             "Pending": int(row.Pending), "Denominator": int(row.Total_Requests),
             "Pending rate": float(row.Pending_Rate),
             "Approved": int(row.Approved), "Denied": int(row.Denied)}
            for row in summary.itertuples(index=False)
        ]
        return {"kind": view, "rows": rows}

    @tool(args_schema=LimitationArguments)
    def report_limitation(reason: str) -> dict:
        """Decline unsupported calculations, questions outside scope, or prohibited guidance."""
        return {"kind": "limitation", "message": LIMITATIONS[reason], "rows": []}

    return {item.name: item for item in (status_totals, category_pending, report_limitation)}
