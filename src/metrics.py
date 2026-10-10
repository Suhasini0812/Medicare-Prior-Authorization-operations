"""Small summary calculations used by the dashboard."""

import pandas as pd


def get_received_date_range(
    requests: pd.DataFrame,
) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """Return the earliest and latest valid received dates, if any exist."""
    received_dates = pd.to_datetime(
        requests["Received_Date"],
        errors="coerce",
    ).dropna()

    if received_dates.empty:
        return None

    return received_dates.min(), received_dates.max()


def get_status_counts(requests: pd.DataFrame) -> pd.DataFrame:
    """Count requests in each status, including blank statuses."""
    statuses = (
        requests["Status"]
        .fillna("Missing status")
        .astype(str)
        .str.strip()
        .replace("", "Missing status")
    )

    counts = statuses.value_counts(sort=False).rename_axis("Status")
    return counts.rename("Requests").reset_index()
