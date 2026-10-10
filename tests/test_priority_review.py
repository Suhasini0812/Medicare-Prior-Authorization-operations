"""Separate priority signals and shared-scope navigation regressions."""

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest

import pandas as pd
import pyarrow as pa
from pandas.testing import assert_frame_equal
from streamlit.testing.v1 import AppTest

from src.data_loader import load_requests
from src.priority_metrics import (
    SUMMARY_COLUMNS, category_summary, highest_pending_rate, largest_pending_workload,
)
from src.reporting import calendar_period, filter_period, filter_scope
from src.snapshot_store import SnapshotStore


APP = Path(__file__).resolve().parents[1] / "app.py"


def rows(categories: dict[str, tuple[int, int]]) -> pd.DataFrame:
    """Small in-memory test fixtures; never replace or edit the supplied CSV."""
    return pd.DataFrame([
        {"Procedure_Category": category, "Status": "Pending" if i < pending else "Approved"}
        for category, (pending, total) in categories.items() for i in range(total)
    ], columns=["Procedure_Category", "Status"])


class PriorityMetricsTests(unittest.TestCase):
    def test_original_counts_and_distinct_leaders(self):
        summary = category_summary(load_requests())
        self.assertEqual(list(summary.columns), list(SUMMARY_COLUMNS))
        self.assertEqual(summary["Total_Requests"].sum(), 500)
        self.assertEqual(summary["Pending"].sum(), 35)
        self.assertEqual(summary["Approved"].sum(), 402)
        self.assertEqual(summary["Denied"].sum(), 63)
        self.assertEqual(summary["Pending"].tolist(), [17, 9, 5, 4])
        workload = largest_pending_workload(summary).iloc[0]
        rate = highest_pending_rate(summary).iloc[0]
        self.assertEqual((workload.Procedure_Category, workload.Pending, workload.Total_Requests),
                         ("Advanced Imaging", 17, 190))
        self.assertEqual((rate.Procedure_Category, rate.Pending, rate.Total_Requests),
                         ("Physical Therapy", 9, 100))
        self.assertEqual(rate.Pending_Rate, 9)

    def test_low_volume_rate_is_not_combined_with_pending_volume(self):
        summary = category_summary(rows({"High volume": (10, 100), "Low volume": (1, 1)}))
        self.assertEqual(largest_pending_workload(summary)["Procedure_Category"].tolist(),
                         ["High volume"])
        self.assertEqual(highest_pending_rate(summary)["Procedure_Category"].tolist(),
                         ["Low volume"])
        self.assertEqual(highest_pending_rate(summary)["Pending_Rate"].tolist(), [100])

    def test_ties_are_exact_and_all_tied_categories_are_returned(self):
        summary = category_summary(rows({"A": (2, 6), "B": (2, 6), "C": (1, 3)}))
        self.assertEqual(largest_pending_workload(summary)["Procedure_Category"].tolist(),
                         ["A", "B"])
        self.assertEqual(highest_pending_rate(summary)["Procedure_Category"].tolist(),
                         ["A", "B", "C"])
        # Same rounded percentage is not necessarily an actual rate tie.
        close = pd.DataFrame({
            "Procedure_Category": ["A", "B"], "Total_Requests": [3000, 3001],
            "Pending": [1, 1],
        })
        self.assertEqual(highest_pending_rate(close)["Procedure_Category"].tolist(), ["A"])

    def test_empty_and_unused_categories_do_not_divide_by_zero(self):
        frame = rows({"Observed": (1, 2)})
        frame["Procedure_Category"] = pd.Categorical(
            frame["Procedure_Category"], categories=["Observed", "Unused"],
        )
        self.assertEqual(category_summary(frame)["Procedure_Category"].tolist(), ["Observed"])
        empty = category_summary(frame.iloc[:0])
        self.assertTrue(empty.empty)
        self.assertEqual(list(empty.columns), list(SUMMARY_COLUMNS))
        self.assertTrue(highest_pending_rate(empty).empty)
        self.assertTrue(largest_pending_workload(empty).empty)
        zero = pd.DataFrame({"Total_Requests": [0], "Pending": [0]})
        self.assertTrue(highest_pending_rate(zero).empty)
        self.assertTrue(largest_pending_workload(zero).empty)

    def test_no_pending_is_a_zero_rate_tie_not_a_missing_category(self):
        summary = category_summary(rows({"A": (0, 2), "B": (0, 3)}))
        self.assertEqual(summary["Pending_Rate"].tolist(), [0, 0])
        self.assertEqual(len(largest_pending_workload(summary)), 2)
        self.assertEqual(len(highest_pending_rate(summary)), 2)


class PriorityNavigationTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "test.sqlite3"
        db_patch = patch("src.snapshot_store.DEFAULT_DB_PATH", self.path)
        db_patch.start()
        self.addCleanup(db_patch.stop)

    def make_app(self):
        app = AppTest.from_file(str(APP), default_timeout=20).run()
        self.assertFalse(app.exception)
        return app

    def test_priority_cleanup_and_workload_sidebar_text(self):
        app = self.make_app()
        self.assertTrue(any(
            "Synthetic demonstration data only" in item.value for item in app.caption
        ))
        app.radio(key="screen").set_value("Priority Review").run()
        self.assertFalse(app.exception)
        headings = [item.value for item in app.header] + [
            item.value for item in app.subheader
        ]
        self.assertIn("Priority Review - Current Data Snapshot", headings)
        self.assertNotIn("Current Data Snapshot", headings)
        self.assertNotIn("Manager Guidance", headings)
        self.assertIn("Largest Pending Workload", headings)
        self.assertIn("Highest Pending Rate", headings)
        captions = " ".join(item.value for item in app.caption)
        self.assertNotIn("These selections update the summary", captions)
        self.assertNotIn("Reporting periods use Received_Date", captions)
        self.assertNotIn(
            "A previous-period comparison is unavailable because this file contains no earlier received-date period.",
            captions,
        )
        self.assertFalse(app.info)
        details = " ".join(item.value for item in app.markdown)
        self.assertIn("Status snapshot date: Not recorded.", details)
        self.assertIn("Rows in snapshot: 500", details)
        self.assertIn("October 1, 2025", details)
        self.assertIn("September 29, 2026", details)
        self.assert_summary(app, load_requests())
        app.radio(key="screen").set_value("Workload Overview").run()
        captions = " ".join(item.value for item in app.caption)
        self.assertNotIn("These selections update the summary", captions)
        self.assertIn("Synthetic demonstration data only", captions)

    def assert_summary(self, app, expected):
        self.assertFalse(app.exception)
        assert_frame_equal(app.dataframe[0].value, category_summary(expected))
        self.assert_charts(app, category_summary(expected))
        self.assertEqual(len(app.sidebar.selectbox(key="selected_snapshot").options), 1)

    def assert_charts(self, app, summary):
        charts = app.get("vega_lite_chart")
        self.assertEqual(len(charts), 2 if not summary.empty else 0)
        for chart, metric in zip(charts, ("Pending", "Pending_Rate")):
            spec = json.loads(chart.proto.spec)
            dataset = next(
                item for item in chart.proto.datasets if item.name == spec["data"]["name"]
            )
            actual = pa.ipc.open_stream(dataset.data.data).read_pandas()
            expected = summary.sort_values(
                [metric, "Procedure_Category"], ascending=[False, True],
            ).reset_index(drop=True)
            assert_frame_equal(actual[list(SUMMARY_COLUMNS)], expected)
            self.assertEqual(spec["encoding"]["y"]["sort"],
                             expected["Procedure_Category"].tolist())

    def test_navigation_reuses_scope_and_ignores_table_only_filters(self):
        app = self.make_app()
        app.radio(key="period_mode").set_value("Month").run()
        app.selectbox(key="month").set_value("2026-08").run()
        app.multiselect(key="categories").set_value(["Advanced Imaging"]).run()
        app.multiselect(key="request_types").set_value(["Standard"]).run()
        app.multiselect(key="table_statuses").set_value(["Denied"]).run()
        app.text_input(key="request_id").set_value("NO_MATCH").run()
        original = load_requests()
        expected = filter_period(
            filter_scope(original, ["Advanced Imaging"], ["Standard"]),
            calendar_period("Month", "2026-08"),
        )
        app.radio(key="screen").set_value("Priority Review").run()
        self.assert_summary(app, expected)
        self.assertEqual(app.header[0].value, "Priority Review - Current Data Snapshot")
        self.assertFalse(any("Synthetic demonstration" in item.value for item in app.info))
        self.assertEqual(app.radio(key="period_mode").value, "Month")
        self.assertEqual(app.selectbox(key="month").value, "2026-08")
        self.assertEqual(app.multiselect(key="categories").value, ["Advanced Imaging"])
        self.assertEqual(app.multiselect(key="request_types").value, ["Standard"])
        # A second rerun must retain Overview's absent widgets as well as scope.
        app.run()
        self.assert_summary(app, expected)
        app.radio(key="screen").set_value("Workload Overview").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "12")
        self.assertEqual(app.metric[1].value, "5")
        self.assertEqual(app.multiselect(key="table_statuses").value, ["Denied"])
        self.assertEqual(app.text_input(key="request_id").value, "NO_MATCH")
        self.assertTrue(app.dataframe[-1].value.empty)

    def test_empty_priority_scope_keeps_cards_and_category_table(self):
        app = self.make_app()
        app.radio(key="screen").set_value("Priority Review").run()
        app.radio(key="period_mode").set_value("Custom").run()
        app.date_input(key="start_date").set_value(date(2027, 1, 1)).run()
        app.date_input(key="end_date").set_value(date(2027, 1, 2)).run()
        self.assertFalse(app.exception)
        self.assertTrue(app.dataframe[0].value.empty)
        self.assert_charts(app, app.dataframe[0].value)
        headings = [item.value for item in app.subheader]
        self.assertIn("Largest Pending Workload", headings)
        self.assertIn("Highest Pending Rate", headings)
        self.assertTrue(any("No requests match" in item.value for item in app.warning))

    def test_pagination_choices_survive_navigation(self):
        app = self.make_app()
        app.selectbox(key="request_page_size").set_value(50).run()
        app.number_input(key="request_page").set_value(2).run()
        before = app.dataframe[-1].value.copy()
        app.radio(key="screen").set_value("Priority Review").run()
        app.run()
        app.radio(key="screen").set_value("Workload Overview").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="request_page_size").value, 50)
        self.assertEqual(app.number_input(key="request_page").value, 2)
        assert_frame_equal(app.dataframe[-1].value, before)

    def test_selected_snapshot_not_original_or_combined_history(self):
        frame = load_requests().head(12).fillna("")
        store = SnapshotStore(self.path)
        saved = store.save_upload(
            "test.csv", frame.to_csv(index=False).encode(), date(2026, 10, 8),
            synthetic_confirmed=True,
        )
        app = self.make_app()
        self.assertEqual(app.selectbox(key="selected_snapshot").value,
                         f"snapshot:{saved.snapshot_id}")
        app.radio(key="screen").set_value("Priority Review").run()
        self.assertFalse(app.exception)
        assert_frame_equal(app.dataframe[0].value, category_summary(frame))
        self.assert_charts(app, category_summary(frame))
        self.assertEqual(app.dataframe[0].value["Total_Requests"].sum(), 12)
        app.selectbox(key="selected_snapshot").set_value("original").run()
        self.assertFalse(app.exception)
        assert_frame_equal(app.dataframe[0].value, category_summary(load_requests()))
        self.assert_charts(app, category_summary(load_requests()))
        self.assertEqual(app.dataframe[0].value["Total_Requests"].sum(), 500)
        self.assertTrue(any("Status snapshot date: Not recorded." in item.value
                            for item in app.markdown))


if __name__ == "__main__":
    unittest.main()
