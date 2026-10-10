"""Reusable Overview controls for uploading and reviewing full snapshots."""

import hashlib
import sqlite3
from datetime import date

import pandas as pd
import streamlit as st

from src.snapshot_store import SnapshotStore


def _fmt(value: str | None) -> str:
    if not value:
        return "Not recorded"
    try:
        return date.fromisoformat(value[:10]).strftime("%b %d, %Y")
    except ValueError:
        return str(value)


def _label(meta: dict) -> str:
    return f"{_fmt(meta['as_of'])}, revision {meta['revision']}"


def _show_missing(missing: pd.DataFrame, previous: dict | None) -> None:
    if previous is None:
        st.info(
            "No earlier dated snapshot exists. The original supplied CSV has an unknown "
            "status capture date and is not a chronological predecessor."
        )
        return
    st.markdown(f"**Comparison snapshot:** {_label(previous)} ({previous['filename']})")
    if missing is None or missing.empty:
        st.caption("No requests that were Pending in the earlier snapshot are absent.")
        return
    ids = ", ".join(missing["PA_Request_ID"].astype(str).head(25))
    more = "" if len(missing) <= 25 else f" and {len(missing) - 25} more"
    st.warning(
        f"{len(missing):,} request(s) recorded as Pending on {_fmt(previous['as_of'])} are absent "
        f"from this snapshot: {ids}{more}. Absence is not treated as resolved, approved, "
        "denied, or removed from scope; it needs manager review."
    )


def _reset_upload_date() -> None:
    """A different file needs its own explicitly entered status capture date."""
    st.session_state["upload_as_of"] = None


def _upload_section(store: SnapshotStore) -> None:
    file = st.file_uploader(
        "Upload monthly snapshot", type=["csv"], key="monthly_uploader",
        help="UTF-8 CSV with the ten documented columns, up to 10 MiB. Larger files are rejected during validation.",
        on_change=_reset_upload_date,
    )
    as_of = st.date_input("Status as-of date", value=None, key="upload_as_of",
                          min_value=date(1677, 9, 22), max_value=date.max,
                          help="The date these statuses were captured. Not inferred from the file.")
    st.caption("Synthetic demonstration data only. Do not upload real member or patient information.")
    if file is None:
        return
    contents = file.getvalue()
    token = hashlib.sha256(contents + str(as_of).encode()).hexdigest()[:16]
    try:
        a = store.assess_upload(contents, as_of)
    except (ValueError, sqlite3.Error) as exc:
        st.error(f"The upload could not be assessed: {exc}")
        return

    frame = a.validation.frame
    for e in a.validation.errors:
        st.error(e)
    for w in a.validation.warnings:
        st.warning(w)
    if not a.validation.valid:
        if frame is not None:
            st.caption(f"{len(frame):,} rows parsed · Validation did not pass.")
        st.error("Invalid upload: it is rejected and cannot be saved.")
        return
    st.info(f"Validation passed · All {len(frame):,} requests checked · Status as-of date: {_fmt(as_of.isoformat())}.")
    _show_missing(a.missing_pending, a.previous)

    confirm_revision = False
    if a.disposition == "duplicate":
        st.info(f"Identical file already saved for this date ({_label(a.existing)}). "
                "Nothing will be saved twice.")
        return
    if a.disposition == "revision":
        st.warning(
            f"A different file is already saved for {_fmt(a.existing['as_of'])} "
            f"(revision {a.existing['revision']}, {a.existing['row_count']:,} rows). "
            "Saving creates a new revision; the earlier revision is preserved."
        )
        confirm_revision = st.checkbox("I confirm creating a new revision",
                                       key=f"revision_confirm_{token}")
    synthetic = st.checkbox("I confirm this file contains synthetic data only",
                            key=f"synthetic_confirmed_{token}")
    ready = (as_of is not None and synthetic
             and (a.disposition != "revision" or confirm_revision))
    if st.button("Save snapshot", type="primary", disabled=not ready, key=f"save_{token}"):
        try:
            res = store.save_upload(file.name, contents, as_of,
                                    confirm_revision=confirm_revision,
                                    synthetic_confirmed=synthetic)
        except (ValueError, sqlite3.Error) as exc:
            st.error(f"Not saved: {exc}")
            return
        if res.disposition == "duplicate":
            st.info("Identical snapshot already exists; nothing was saved.")
            return
        saved, _ = store.load_snapshot(res.snapshot_id)
        st.session_state["requested_snapshot"] = f"snapshot:{res.snapshot_id}"
        st.session_state["monthly_feedback"] = (
            f"Saved {file.name} as {_label(saved)} with {saved['row_count']:,} rows. "
            "The newly saved snapshot is now selected. Earlier snapshots remain available."
        )
        st.rerun()


def render_upload_controls(store: SnapshotStore) -> None:
    """Show a compact upload form; saving still requires validation and consent."""
    feedback = st.session_state.pop("monthly_feedback", None)
    if feedback:
        st.success(feedback)
    _upload_section(store)


def render_snapshot_review(store: SnapshotStore, selected_snapshot_id: int) -> None:
    """Keep absence warnings accessible without rendering a history list."""
    try:
        review = store.review_snapshot(selected_snapshot_id)
        if not review.missing_pending.empty:
            with st.expander(
                f"Missing-Pending review · {len(review.missing_pending):,} absent request(s)",
                expanded=False,
            ):
                _show_missing(review.missing_pending, review.previous)
    except (ValueError, sqlite3.Error) as exc:
        st.error(f"Snapshot data could not be read: {exc}")
