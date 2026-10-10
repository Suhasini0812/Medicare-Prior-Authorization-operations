"""Append-only local SQLite snapshots, with atomic revision checks."""

from dataclasses import dataclass
from contextlib import contextmanager
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sqlite3

import pandas as pd

from src.data_loader import PROJECT_ROOT, REQUIRED_COLUMNS
from src.snapshot_validation import ValidationResult, content_fingerprint, validate_upload


DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "snapshots.sqlite3"


@dataclass
class SnapshotReview:
    previous: dict | None
    missing_pending: pd.DataFrame


@dataclass
class UploadAssessment:
    validation: ValidationResult
    disposition: str
    existing: dict | None
    previous: dict | None
    missing_pending: pd.DataFrame


@dataclass
class SaveResult:
    disposition: str
    snapshot_id: int


class SnapshotStore:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path is not None else DEFAULT_DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY,
                    as_of TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    row_count INTEGER NOT NULL,
                    accepted_at TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    UNIQUE(as_of, revision),
                    UNIQUE(as_of, content_hash)
                );
                CREATE TABLE IF NOT EXISTS snapshot_requests (
                    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
                    row_number INTEGER NOT NULL,
                    pa_request_id TEXT NOT NULL,
                    row_json TEXT NOT NULL,
                    PRIMARY KEY(snapshot_id, row_number),
                    UNIQUE(snapshot_id, pa_request_id)
                );
            """)

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _metadata(row) -> dict | None:
        return dict(row) if row is not None else None

    def list_snapshots(self) -> list[dict]:
        with self._connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM snapshots ORDER BY as_of DESC, revision DESC"
            )]

    @staticmethod
    def _frame(db, snapshot_id: int) -> pd.DataFrame:
        records = [
            json.loads(row["row_json"])
            for row in db.execute(
                "SELECT row_json FROM snapshot_requests WHERE snapshot_id=? ORDER BY row_number",
                (snapshot_id,),
            )
        ]
        return pd.DataFrame(records, columns=REQUIRED_COLUMNS)

    def load_snapshot(self, snapshot_id: int) -> tuple[dict, pd.DataFrame]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM snapshots WHERE id=?", (snapshot_id,)).fetchone()
            if row is None:
                raise ValueError("This saved snapshot is not available. Select another snapshot.")
            return dict(row), self._frame(db, snapshot_id)

    @staticmethod
    def _previous(db, as_of: str, revision: int | None = None):
        # A revision's predecessor may be the earlier revision on the same date.
        # New dates compare with the latest accepted snapshot no later than that date.
        if revision is None:
            return db.execute(
                "SELECT * FROM snapshots WHERE as_of<=? ORDER BY as_of DESC, revision DESC LIMIT 1",
                (as_of,),
            ).fetchone()
        return db.execute(
            """SELECT * FROM snapshots WHERE as_of<? OR (as_of=? AND revision<?)
               ORDER BY as_of DESC, revision DESC LIMIT 1""",
            (as_of, as_of, revision),
        ).fetchone()

    def _review(self, db, frame: pd.DataFrame, previous) -> SnapshotReview:
        missing = pd.DataFrame(columns=REQUIRED_COLUMNS)
        if previous is not None:
            earlier = self._frame(db, previous["id"])
            missing = earlier.loc[
                earlier["Status"].eq("Pending")
                & ~earlier["PA_Request_ID"].isin(frame["PA_Request_ID"])
            ].copy()
        return SnapshotReview(self._metadata(previous), missing)

    def review_snapshot(self, snapshot_id: int) -> SnapshotReview:
        with self._connect() as db:
            row = db.execute("SELECT * FROM snapshots WHERE id=?", (snapshot_id,)).fetchone()
            if row is None:
                raise ValueError("This saved snapshot is no longer available.")
            return self._review(
                db, self._frame(db, snapshot_id),
                self._previous(db, row["as_of"], row["revision"]),
            )

    def assess_upload(self, contents: bytes, as_of: date | None) -> UploadAssessment:
        validation = validate_upload(contents, as_of)
        empty = pd.DataFrame(columns=REQUIRED_COLUMNS)
        if not validation.valid:
            return UploadAssessment(validation, "invalid", None, None, empty)
        fingerprint = content_fingerprint(validation.frame)
        with self._connect() as db:
            same = db.execute(
                "SELECT * FROM snapshots WHERE as_of=? AND content_hash=?",
                (as_of.isoformat(), fingerprint),
            ).fetchone()
            latest = db.execute(
                "SELECT * FROM snapshots WHERE as_of=? ORDER BY revision DESC LIMIT 1",
                (as_of.isoformat(),),
            ).fetchone()
            if same is not None:
                review = self._review(
                    db, validation.frame,
                    self._previous(db, same["as_of"], same["revision"]),
                )
                return UploadAssessment(validation, "duplicate", dict(same), review.previous, review.missing_pending)
            review = self._review(db, validation.frame, self._previous(db, as_of.isoformat()))
            return UploadAssessment(
                validation, "revision" if latest is not None else "new",
                self._metadata(latest), review.previous, review.missing_pending,
            )

    def save_upload(
        self, filename: str, contents: bytes, as_of: date | None, *,
        confirm_revision: bool = False, synthetic_confirmed: bool = False,
    ) -> SaveResult:
        # UI validation is informational: enforce all rules again at the write boundary.
        validation = validate_upload(contents, as_of)
        if not validation.valid:
            raise ValueError("Upload not saved: " + " ".join(validation.errors))
        if not synthetic_confirmed:
            raise ValueError("Confirm that this upload contains synthetic demonstration data only.")
        fingerprint = content_fingerprint(validation.frame)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            same = db.execute(
                "SELECT id FROM snapshots WHERE as_of=? AND content_hash=?",
                (as_of.isoformat(), fingerprint),
            ).fetchone()
            if same is not None:
                return SaveResult("duplicate", same["id"])
            latest = db.execute(
                "SELECT revision FROM snapshots WHERE as_of=? ORDER BY revision DESC LIMIT 1",
                (as_of.isoformat(),),
            ).fetchone()
            if latest is not None and not confirm_revision:
                raise ValueError("A snapshot already exists for this date. Confirm a new revision; earlier revisions are preserved.")
            revision = latest["revision"] + 1 if latest is not None else 1
            cursor = db.execute(
                """INSERT INTO snapshots(as_of,revision,filename,row_count,accepted_at,content_hash)
                   VALUES(?,?,?,?,?,?)""",
                (
                    as_of.isoformat(), revision, Path(filename.replace("\\", "/")).name,
                    len(validation.frame), datetime.now(timezone.utc).isoformat(), fingerprint,
                ),
            )
            snapshot_id = cursor.lastrowid
            db.executemany(
                "INSERT INTO snapshot_requests(snapshot_id,row_number,pa_request_id,row_json) VALUES(?,?,?,?)",
                [
                    (snapshot_id, position, row["PA_Request_ID"],
                     json.dumps(row, ensure_ascii=False))
                    for position, row in enumerate(validation.frame.to_dict(orient="records"))
                ],
            )
            return SaveResult("revision" if latest is not None else "new", snapshot_id)
