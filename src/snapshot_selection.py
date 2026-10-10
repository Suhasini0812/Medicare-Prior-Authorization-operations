"""Resolve one explicitly selected snapshot; never combine snapshot rows."""

import pandas as pd

from src.data_loader import load_requests
from src.snapshot_store import SnapshotStore


ORIGINAL_OPTION = "original"


def snapshot_options(snapshots: list[dict]) -> list[str]:
    """Store history is date/revision descending; the undated original is last."""
    return [f"snapshot:{item['id']}" for item in snapshots] + [ORIGINAL_OPTION]


def load_selected_snapshot(
    store: SnapshotStore, selection: str
) -> tuple[pd.DataFrame, dict | None]:
    if selection == ORIGINAL_OPTION:
        return load_requests(), None
    if not selection.startswith("snapshot:"):
        raise ValueError("Unknown snapshot selection.")
    metadata, frame = store.load_snapshot(int(selection.split(":", 1)[1]))
    return frame, metadata
