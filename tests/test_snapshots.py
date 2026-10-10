"""Synthetic snapshot validation, atomic persistence and selection regressions."""

from datetime import date
from contextlib import closing
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src.data_loader import DATA_FILE, load_requests
from src.snapshot_selection import ORIGINAL_OPTION, load_selected_snapshot, snapshot_options
from src.snapshot_store import SnapshotStore
from src.snapshot_validation import validate_upload
from src.reporting import ReportingPeriod, calendar_period, filter_period


AS_OF = date(2026, 10, 31)
APP = Path(__file__).resolve().parents[1] / "app.py"


def csv_bytes(frame):
    return frame.to_csv(index=False).encode("utf-8")


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "snapshots.sqlite3"
        self.store = SnapshotStore(self.path)
        original = load_requests().fillna("")
        self.frame = original.groupby("Status", sort=False).head(1).copy().reset_index(drop=True).astype(str)
        self.contents = csv_bytes(self.frame)

    def save(self, frame=None, as_of=AS_OF, **kwargs):
        return self.store.save_upload(
            "synthetic.csv", csv_bytes(self.frame if frame is None else frame), as_of,
            synthetic_confirmed=True, **kwargs,
        )

    def assert_invalid(self, frame, message):
        result = validate_upload(csv_bytes(frame), AS_OF)
        self.assertFalse(result.valid)
        self.assertTrue(any(message in text for text in result.errors), result.errors)
        with self.assertRaises(ValueError):
            self.save(frame)
        self.assertEqual(self.store.list_snapshots(), [])

    def test_original_validates_without_modifying_supplied_file(self):
        before = DATA_FILE.read_bytes()
        result = validate_upload(before, AS_OF)
        self.assertTrue(result.valid, result.errors)
        self.assertEqual(len(result.frame), 500)
        self.assertEqual(DATA_FILE.read_bytes(), before)
        self.assertEqual(self.store.list_snapshots(), [])

    def test_missing_columns_and_required_values_are_blocked(self):
        self.assert_invalid(self.frame.drop(columns="Status"), "Missing required columns")
        for column in ("PA_Request_ID", "Received_Date", "Procedure_Category", "Request_Type",
                       "Status", "Documentation_Status", "Additional_Info_Requested", "Resubmission_Count"):
            with self.subTest(column=column):
                frame = self.frame.copy()
                frame.loc[0, column] = ""
                self.assert_invalid(frame, column)

    def test_dates_statuses_and_counts_are_validated(self):
        for column, value in (
            ("Received_Date", "2026-02-30"), ("Decision_Date", "not-a-date"),
            ("Received_Date", "12/01/2025"), ("Received_Date", "1500-01-01"),
            ("Received_Date", "2027-01-01"), ("Decision_Date", "2020-01-01"),
            ("Status", "Resolved"), ("Request_Type", "Unknown"),
            ("Documentation_Status", "Unknown"), ("Additional_Info_Requested", "Maybe"),
            ("Resubmission_Count", "-1"), ("Resubmission_Count", "1.5"),
        ):
            with self.subTest(column=column, value=value):
                frame = self.frame.copy()
                frame.loc[0, column] = value
                self.assert_invalid(frame, column)

    def test_malformed_empty_extra_columns_and_missing_as_of(self):
        for contents in (
            b"", b"\xff", b"Status\nApproved", b"Status,Status\nApproved,Pending",
            self.contents.splitlines()[0] + b"\nwrong,field,count\n",
            csv_bytes(self.frame.iloc[:0]), csv_bytes(self.frame.assign(Member_Name="not allowed")),
        ):
            with self.subTest(contents=contents[:25]):
                self.assertFalse(validate_upload(contents, AS_OF).valid)
        result = validate_upload(self.contents, None)
        self.assertFalse(result.valid)
        with self.assertRaises(ValueError):
            self.store.save_upload("synthetic.csv", self.contents, None, synthetic_confirmed=True)
        self.assertEqual(self.store.list_snapshots(), [])

    def test_duplicate_ids_in_upload_are_blocked_after_trimming(self):
        frame = self.frame.copy()
        frame.loc[1, "PA_Request_ID"] = " " + frame.loc[0, "PA_Request_ID"] + " "
        self.assert_invalid(frame, "Duplicate IDs")

    def test_optional_missing_decision_date_is_not_invented(self):
        frame = self.frame.copy()
        frame["Decision_Date"] = ""
        result = validate_upload(csv_bytes(frame), AS_OF)
        self.assertTrue(result.valid, result.errors)
        self.assertTrue(result.warnings)
        saved = self.save(frame)
        _, loaded = self.store.load_snapshot(saved.snapshot_id)
        self.assertTrue(loaded["Decision_Date"].eq("").all())

    def test_synthetic_acknowledgment_required(self):
        with self.assertRaisesRegex(ValueError, "synthetic"):
            self.store.save_upload("synthetic.csv", self.contents, AS_OF)
        self.assertEqual(self.store.list_snapshots(), [])

    def test_identical_upload_same_date_is_idempotent_even_after_reordering(self):
        saved = self.save()
        reordered = self.frame.iloc[::-1, ::-1]
        again = self.store.save_upload(
            "another-name.csv", csv_bytes(reordered), AS_OF, synthetic_confirmed=True,
        )
        self.assertEqual(again.disposition, "duplicate")
        self.assertEqual(again.snapshot_id, saved.snapshot_id)
        self.assertEqual(len(self.store.list_snapshots()), 1)
        assessment = self.store.assess_upload(self.contents, AS_OF)
        self.assertEqual(assessment.disposition, "duplicate")

    def test_same_date_revision_requires_confirmation_and_preserves_earlier(self):
        first = self.save()
        changed = self.frame.copy()
        changed.loc[0, "Documentation_Status"] = "Incomplete"
        if changed.equals(self.frame):
            changed.loc[0, "Documentation_Status"] = "Complete"
        assessment = self.store.assess_upload(csv_bytes(changed), AS_OF)
        self.assertEqual(assessment.disposition, "revision")
        with self.assertRaisesRegex(ValueError, "Confirm"):
            self.save(changed)
        self.assertEqual(len(self.store.list_snapshots()), 1)
        second = self.save(changed, confirm_revision=True)
        first_meta, first_rows = self.store.load_snapshot(first.snapshot_id)
        second_meta, second_rows = self.store.load_snapshot(second.snapshot_id)
        self.assertEqual((first_meta["revision"], second_meta["revision"]), (1, 2))
        self.assertFalse(first_rows.equals(second_rows))
        self.assertEqual(len(first_rows), len(self.frame))
        self.assertEqual(self.save().disposition, "duplicate")
        self.assertEqual(len(self.store.list_snapshots()), 2)

    def test_invalid_revision_never_partially_saves(self):
        first = self.save()
        invalid = self.frame.copy()
        invalid.loc[0, "Status"] = "invalid"
        with self.assertRaises(ValueError):
            self.save(invalid, confirm_revision=True)
        self.assertEqual(len(self.store.list_snapshots()), 1)
        self.assertEqual(len(self.store.load_snapshot(first.snapshot_id)[1]), 3)

    def test_missing_pending_revision_compares_to_previous_revision(self):
        first = self.save()
        without_pending = self.frame.loc[~self.frame["Status"].eq("Pending")]
        second = self.save(without_pending, confirm_revision=True)
        review = self.store.review_snapshot(second.snapshot_id)
        self.assertEqual(review.previous["id"], first.snapshot_id)
        self.assertEqual(len(review.missing_pending), 1)
        self.assertEqual(review.previous["as_of"], AS_OF.isoformat())

    def test_sql_failure_rolls_back_snapshot_header_and_all_rows(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""
                CREATE TRIGGER fail_rows BEFORE INSERT ON snapshot_requests
                WHEN NEW.row_number=1 BEGIN SELECT RAISE(ABORT,'test failure'); END
            """)
        with self.assertRaises(sqlite3.IntegrityError):
            self.save()
        self.assertEqual(self.store.list_snapshots(), [])
        with closing(sqlite3.connect(self.path)) as db, db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM snapshot_requests").fetchone()[0], 0)

    def test_missing_pending_and_request_ids_across_snapshots(self):
        first = self.save()
        second_frame = self.frame.loc[~self.frame["Status"].eq("Pending")].copy()
        missing_id = self.frame.loc[self.frame["Status"].eq("Pending"), "PA_Request_ID"].iloc[0]
        assessment = self.store.assess_upload(csv_bytes(second_frame), date(2026, 11, 30))
        self.assertEqual(assessment.missing_pending["PA_Request_ID"].tolist(), [missing_id])
        second = self.save(second_frame, date(2026, 11, 30))
        review = self.store.review_snapshot(second.snapshot_id)
        self.assertEqual(review.previous["id"], first.snapshot_id)
        self.assertEqual(review.missing_pending["Status"].tolist(), ["Pending"])
        self.assertEqual(self.store.load_snapshot(first.snapshot_id)[1]["Status"].tolist(), self.frame["Status"].tolist())
        self.assertEqual(len(self.store.load_snapshot(second.snapshot_id)[1]), 2)

    def test_predecessor_is_as_of_order_not_upload_order_and_survives_restart(self):
        late = self.save(as_of=date(2027, 2, 28))
        early = self.save(as_of=date(2026, 10, 31))
        middle = self.save(as_of=date(2027, 1, 31))
        reopened = SnapshotStore(self.path)
        self.assertEqual(reopened.list_snapshots()[0]["id"], late.snapshot_id)
        self.assertEqual(reopened.review_snapshot(middle.snapshot_id).previous["id"], early.snapshot_id)
        self.assertEqual(reopened.review_snapshot(late.snapshot_id).previous["id"], middle.snapshot_id)
        self.assertIsNone(reopened.review_snapshot(early.snapshot_id).previous)

    def test_overview_selection_newest_revision_old_revision_and_original(self):
        first = self.save()
        second = self.save(self.frame.iloc[:2], date(2026, 11, 30))
        options = snapshot_options(self.store.list_snapshots())
        self.assertEqual(options[0], f"snapshot:{second.snapshot_id}")
        self.assertEqual(options[-1], ORIGINAL_OPTION)
        selected, meta = load_selected_snapshot(self.store, options[0])
        self.assertEqual(len(selected), 2)
        self.assertEqual(meta["as_of"], "2026-11-30")
        with patch("src.snapshot_store.DEFAULT_DB_PATH", self.path):
            app = AppTest.from_file(str(APP), default_timeout=20).run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.metric[0].value, "2")
            request_list = app.dataframe[-1].value
            self.assertEqual(len(request_list), 2)
            app.multiselect(key="table_statuses").set_value(["Pending"]).run()
            app.sidebar.selectbox(key="selected_snapshot").set_value(f"snapshot:{first.snapshot_id}").run()
            self.assertEqual(app.metric[0].value, "3")
            self.assertEqual(app.multiselect(key="table_statuses").value, [])
            request_list = app.dataframe[-1].value
            self.assertEqual(len(request_list), 3)
            app.sidebar.selectbox(key="selected_snapshot").set_value(ORIGINAL_OPTION).run()
            self.assertEqual(app.metric[0].value, "500")
            self.assertTrue(any(
                "Status snapshot date: Not recorded." in item.value for item in app.markdown
            ))
            self.assertEqual(app.radio(key="screen").value, "Workload Overview")
            self.assertEqual(app.title[0].value, "Prior Authorization Operations Dashboard")
            self.assertEqual(app.header[0].value, "Prior Authorization Workload Review")
            self.assertFalse(app.get("popover"))
            self.assertEqual(app.get("file_uploader")[0].proto.label, "Upload monthly snapshot")
            self.assertEqual(app.sidebar.selectbox(key="selected_snapshot").label, "Snapshot to view")
            self.assertFalse(any(item.label == "Snapshot history" for item in app.expander))
            self.assertIsNone(app.date_input(key="upload_as_of").value)

    def test_upload_from_overview_selects_newly_saved_backdated_snapshot(self):
        newer = self.save(as_of=date(2026, 12, 31))
        file = SimpleNamespace(name="backdated.csv", getvalue=lambda: self.contents)
        with patch("src.snapshot_store.DEFAULT_DB_PATH", self.path), patch(
            "src.monthly_data.st.file_uploader", return_value=file,
        ):
            app = AppTest.from_file(str(APP), default_timeout=20).run()
            self.assertEqual(app.session_state["selected_snapshot"], f"snapshot:{newer.snapshot_id}")
            app.date_input(key="upload_as_of").set_value(AS_OF).run()
            consent = next(item for item in app.checkbox if "synthetic data only" in item.label)
            consent.check().run()
            self.assertEqual(len(app.success), 0)
            self.assertEqual(len(app.dataframe), 1)  # Only the paginated request list.
            self.assertFalse(any("Review before saving" in item.value for item in app.markdown))
            save = next(item for item in app.button if item.label == "Save snapshot")
            save.click().run()
            self.assertEqual(len(app.exception), 0)
            saved = next(item for item in self.store.list_snapshots() if item["as_of"] == AS_OF.isoformat())
            self.assertEqual(app.session_state["selected_snapshot"], f"snapshot:{saved['id']}")
            self.assertTrue(any("newly saved snapshot is now selected" in item.value for item in app.success))
            self.assertEqual(len(self.store.list_snapshots()), 2)
            self.assertEqual(self.store.list_snapshots()[0]["id"], newer.snapshot_id)

    def test_invalid_upload_beyond_first_page_cannot_be_saved(self):
        frame = load_requests().fillna("").astype(str).head(60).copy()
        frame.loc[frame.index[-1], "Status"] = "Invalid"
        file = SimpleNamespace(name="invalid.csv", getvalue=lambda: csv_bytes(frame))
        with patch("src.snapshot_store.DEFAULT_DB_PATH", self.path), patch(
            "src.monthly_data.st.file_uploader", return_value=file,
        ):
            app = AppTest.from_file(str(APP), default_timeout=20).run()
            app.date_input(key="upload_as_of").set_value(AS_OF).run()
            self.assertEqual(len(app.exception), 0)
            self.assertTrue(any("Invalid upload" in item.value for item in app.error))
            self.assertFalse(any(item.label == "Save snapshot" for item in app.button))
            self.assertEqual(len(app.success), 0)
            self.assertEqual(len(app.dataframe), 1)
            self.assertEqual(self.store.list_snapshots(), [])

    def test_received_date_modes_do_not_switch_selected_snapshot(self):
        earlier = self.save()
        self.save(self.frame.iloc[:2], date(2026, 11, 30))
        with patch("src.snapshot_store.DEFAULT_DB_PATH", self.path):
            app = AppTest.from_file(str(APP), default_timeout=20).run()
            selection = f"snapshot:{earlier.snapshot_id}"
            app.sidebar.selectbox(key="selected_snapshot").set_value(selection).run()
            for mode in ("Month", "Quarter", "Year", "Custom", "All available data"):
                app.sidebar.radio(key="period_mode").set_value(mode).run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(app.sidebar.selectbox(key="selected_snapshot").value, selection)
                self.assertEqual(app.session_state["selected_snapshot"], selection)
                if mode in ("Month", "Quarter", "Year"):
                    key = mode.lower()
                    period = calendar_period(mode, str(app.sidebar.selectbox(key=key).value))
                elif mode == "Custom":
                    period = ReportingPeriod(
                        mode, app.date_input(key="start_date").value,
                        app.date_input(key="end_date").value,
                    )
                else:
                    period = ReportingPeriod(
                        mode, date.fromisoformat(self.frame.Received_Date.min()),
                        date.fromisoformat(self.frame.Received_Date.max()),
                    )
                expected = filter_period(self.frame, period)
                self.assertEqual(
                    [metric.value for metric in app.metric],
                    [str(len(expected)), *[
                        str(int(expected.Status.eq(status).sum()))
                        for status in ("Pending", "Approved", "Denied")
                    ]],
                )
                self.assertEqual(len(app.dataframe[-1].value), len(expected))


if __name__ == "__main__":
    unittest.main()
