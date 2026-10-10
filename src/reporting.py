"""Reporting-period and filtering rules; these never change the source CSV."""

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd


STATUSES = ("Approved", "Denied", "Pending")


@dataclass(frozen=True)
class ReportingPeriod:
    mode: str
    start: date
    end: date


def calendar_period(mode: str, value: str) -> ReportingPeriod:
    """Turn a calendar month, quarter, or year into inclusive date bounds."""
    frequency = {"Month": "M", "Quarter": "Q", "Year": "Y"}[mode]
    period = pd.Period(value, freq=frequency)
    return ReportingPeriod(mode, period.start_time.date(), period.end_time.date())


def previous_period(period: ReportingPeriod) -> ReportingPeriod:
    """Use the previous calendar period, or equal-length adjacent custom dates."""
    if period.mode in ("Month", "Quarter", "Year"):
        frequency = {"Month": "M", "Quarter": "Q", "Year": "Y"}[period.mode]
        previous = pd.Period(period.start, freq=frequency) - 1
        return ReportingPeriod(
            period.mode, previous.start_time.date(), previous.end_time.date()
        )
    length = (period.end - period.start).days + 1
    return ReportingPeriod(
        period.mode, period.start - timedelta(days=length),
        period.start - timedelta(days=1),
    )


def filter_scope(
    requests: pd.DataFrame, categories: list[str], request_types: list[str]
) -> pd.DataFrame:
    """Empty selections mean all categories/types."""
    selected = requests
    if categories:
        selected = selected.loc[selected["Procedure_Category"].isin(categories)]
    if request_types:
        selected = selected.loc[selected["Request_Type"].isin(request_types)]
    return selected.copy()


def filter_period(
    requests: pd.DataFrame, period: ReportingPeriod
) -> pd.DataFrame:
    dates = pd.to_datetime(requests["Received_Date"], errors="coerce").dt.normalize()
    mask = dates.between(pd.Timestamp(period.start), pd.Timestamp(period.end))
    return requests.loc[mask].copy()


def filter_table(
    requests: pd.DataFrame, statuses: list[str], request_id: str
) -> pd.DataFrame:
    """Table-only filters must not affect the summary denominator."""
    selected = requests
    if statuses:
        selected = selected.loc[selected["Status"].isin(statuses)]
    if request_id.strip():
        matches = selected["PA_Request_ID"].astype("string").str.contains(
            request_id.strip(), case=False, regex=False, na=False
        )
        selected = selected.loc[matches]
    return selected.copy()


def status_summary(requests: pd.DataFrame) -> dict:
    total = len(requests)
    counts = {
        status: int(requests["Status"].eq(status).sum()) for status in STATUSES
    }
    return {
        "total": total,
        "counts": counts,
        "percentages": {
            status: count / total * 100 if total else None
            for status, count in counts.items()
        },
    }


def comparison_availability(
    scoped: pd.DataFrame, period: ReportingPeriod, coverage: tuple[date, date]
) -> tuple[bool, str]:
    previous = previous_period(period)
    if period.start < coverage[0] or period.end > coverage[1]:
        return False, "The selected period extends beyond observed received-date coverage."
    if previous.start < coverage[0] or previous.end > coverage[1]:
        return False, "The previous equivalent period extends beyond observed received-date coverage."
    if filter_period(scoped, period).empty or filter_period(scoped, previous).empty:
        return False, "One or both periods have no requests for the selected category/type filters."
    return True, "Both date windows are within observed coverage; this does not prove period completeness."


def comparison_table(current: pd.DataFrame, previous: pd.DataFrame) -> pd.DataFrame:
    now, before = status_summary(current), status_summary(previous)
    rows = []
    for status in ("Total requests", *STATUSES):
        is_total = status == "Total requests"
        n = now["total"] if is_total else now["counts"][status]
        p = before["total"] if is_total else before["counts"][status]
        current_share = None if is_total else now["percentages"][status]
        previous_share = None if is_total else before["percentages"][status]
        rows.append({
            "Measure": "Denied (descriptive)" if status == "Denied" else status,
            "Selected count": n,
            "Previous count": p,
            "Count change": n - p,
            "Selected share / denominator": (
                "—" if is_total else f"{current_share:.1f}% ({n}/{now['total']})"
            ),
            "Previous share / denominator": (
                "—" if is_total else f"{previous_share:.1f}% ({p}/{before['total']})"
            ),
            "Share change (percentage points)": (
                "—" if is_total else f"{current_share - previous_share:+.1f}"
            ),
        })
    return pd.DataFrame(rows)
