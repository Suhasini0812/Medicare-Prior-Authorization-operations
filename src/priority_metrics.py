"""Category-level investigation signals, calculated from one reporting cohort."""

from fractions import Fraction

import pandas as pd


SUMMARY_COLUMNS = (
    "Procedure_Category", "Total_Requests", "Pending", "Pending_Rate",
    "Approved", "Denied",
)


def category_summary(requests: pd.DataFrame) -> pd.DataFrame:
    """Count recorded statuses by category; rates use all requests in that category."""
    summary = requests.groupby(
        "Procedure_Category", observed=True, dropna=False,
    ).agg(
        Total_Requests=("Status", "size"),
        Pending=("Status", lambda values: int(values.eq("Pending").sum())),
        Approved=("Status", lambda values: int(values.eq("Approved").sum())),
        Denied=("Status", lambda values: int(values.eq("Denied").sum())),
    ).reset_index()
    # Unused categorical labels are not zero-request findings.
    summary = summary.loc[summary["Total_Requests"].gt(0)].copy()
    summary["Pending_Rate"] = summary["Pending"] / summary["Total_Requests"] * 100
    return summary.loc[:, SUMMARY_COLUMNS].sort_values(
        ["Pending", "Procedure_Category"], ascending=[False, True],
    ).reset_index(drop=True)


def largest_pending_workload(summary: pd.DataFrame) -> pd.DataFrame:
    """Return every category tied for the greatest recorded Pending count."""
    eligible = summary.loc[summary["Total_Requests"].gt(0)]
    if eligible.empty:
        return eligible.copy()
    return eligible.loc[eligible["Pending"].eq(eligible["Pending"].max())].copy()


def highest_pending_rate(summary: pd.DataFrame) -> pd.DataFrame:
    """Return exact rate ties, without ranking on rounded display percentages."""
    eligible = summary.loc[summary["Total_Requests"].gt(0)]
    if eligible.empty:
        return eligible.copy()
    rates = [
        Fraction(int(pending), int(total))
        for pending, total in zip(eligible["Pending"], eligible["Total_Requests"])
    ]
    highest = max(rates)
    return eligible.loc[[rate == highest for rate in rates]].copy()
