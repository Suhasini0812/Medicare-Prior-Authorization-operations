"""Exercise the real Streamlit controls without a separate browser service."""

import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch
from datetime import date, timedelta
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.data_loader import load_requests
from src.reporting import comparison_table


APP = Path(__file__).resolve().parents[1] / "app.py"


class OverviewTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        db_patch = patch("src.snapshot_store.DEFAULT_DB_PATH", Path(directory.name) / "test.sqlite3")
        db_patch.start()
        self.addCleanup(db_patch.stop)

    def make_app(self):
        app = AppTest.from_file(str(APP), default_timeout=20).run()
        self.assertEqual(len(app.exception), 0)
        return app

    def assert_counts(self, app, rows):
        self.assertEqual(len(app.exception), 0)
        expected = [len(rows), *[
            int(rows["Status"].eq(status).sum())
            for status in ("Pending", "Approved", "Denied")
        ]]
        self.assertEqual([m.value for m in app.metric], [f"{n:,}" for n in expected])
        expected_shares = ["100%", *[
            f"{count / len(rows) * 100:.1f}%" if len(rows) else "Not available"
            for count in expected[1:]
        ]]
        self.assertEqual([m.delta for m in app.metric], expected_shares)
        bars = [
            item.value for item in app.markdown
            if item.value.startswith('<div class="workload-share-track"')
        ]
        self.assertEqual(len(bars), 4)
        fills = [100, *[
            count / len(rows) * 100 if len(rows) else 0 for count in expected[1:]
        ]]
        for bar, percentage in zip(bars, fills):
            self.assertIn(f'width:{percentage:.6f}%', bar)
        self.assertFalse(any(
            text in caption.value for caption in app.caption
            for text in ("In the selected reporting scope", "Recorded pending requests",
                         "Descriptive rate · Not a quality score")
        ))
        self.assertFalse(any(
            f" of {len(rows):,}" in caption.value
            for caption in app.caption
            if "Showing rows" not in caption.value
        ))

    def test_manager_facing_copy_and_active_summary_filters(self):
        app = self.make_app()
        self.assertEqual(app.title[0].value, "Prior Authorization Operations Dashboard")
        self.assertEqual(app.header[0].value, "Prior Authorization Workload Review")
        self.assertTrue(any(
            "Status snapshot date: Not recorded." in text.value
            for text in app.markdown
        ))
        self.assertTrue(any(
            "The date when these statuses were captured is unknown." in text.value
            for text in app.markdown
        ))
        self.assertTrue(any(
            "### PA Operations" == text.value
            for text in app.sidebar.markdown
        ))
        captions = [text.value for text in app.caption]
        self.assertNotIn(
            "Review request volume and recorded status, then inspect the requests behind the summary.",
            captions,
        )
        self.assertNotIn("These selections update the summary and request list.", captions)
        self.assertNotIn(
            "Reporting periods use Received_Date; statuses come from the selected snapshot.",
            captions,
        )
        self.assertIn(
            "These controls narrow the request list below; they do not change the summary cards.",
            captions,
        )
        self.assertFalse(any("Only Overview" in text for text in captions))
        self.assertFalse(any("Table-only" in text for text in captions))
        self.assertFalse(any("Active summary filters" in text for text in captions))
        self.assertFalse(any("Request list filters ·" in text for text in captions))
        self.assertFalse(any(
            "matching records**" in item.value and "in the reporting scope" in item.value
            for item in app.markdown
        ))
        self.assertTrue(any(
            'text-align: right' in item.value and "Rows in snapshot: 500" in item.value
            for item in app.markdown
        ))
        self.assertEqual(len(app.checkbox), 0)
        self.assertNotIn(
            "A previous-period comparison is unavailable because this file contains no earlier received-date period.",
            [text.value for text in app.sidebar.caption],
        )
        self.assertIn("About this data", [item.label for item in app.expander])
        self.assertFalse(app.get("popover"))
        self.assertEqual(app.get("file_uploader")[0].proto.label, "Upload monthly snapshot")
        self.assertIn("Prior Authorization Data", [item.value for item in app.subheader])
        self.assertNotIn("Request list", [item.value for item in app.subheader])
        self.assertFalse(any("Filename:" in item.value for item in app.markdown))
        self.assertNotIn("Snapshot history", [item.label for item in app.expander])
        self.assertEqual(app.sidebar.selectbox(key="selected_snapshot").label, "Snapshot to view")
        self.assertFalse(any(item.key == "selected_snapshot" for item in app.main.selectbox))
        self.assertEqual(app.sidebar.radio(key="period_mode").label, "Received-date reporting period")
        self.assertLess(
            [item.value for item in app.subheader].index("Current Data Snapshot"),
            [item.value for item in app.subheader].index("Workload at a Glance"),
        )
        self.assertEqual(app.radio(key="screen").value, "Workload Overview")
        self.assertFalse(any("Selected reporting period" in text for text in captions))
        self.assertEqual(app.multiselect(key="table_statuses").label, "Status")
        app.multiselect(key="table_statuses").set_value(["Pending"]).run()
        self.assertFalse(any(
            "Active summary filters" in text.value for text in app.caption
        ))
        app.multiselect(key="categories").set_value(["Cardiology"]).run()
        self.assertTrue(any(
            "Active summary filters · Procedure category: Cardiology" == text.value
            for text in app.caption
        ))
        app.sidebar.button[0].click().run()
        self.assertFalse(any(
            "Active summary filters" in text.value for text in app.caption
        ))

    def test_baseline_table_filters_and_reset(self):
        app = self.make_app()
        rows = load_requests()
        self.assert_counts(app, rows)
        self.assertEqual(len(app.dataframe[-1].value), 25)
        app.multiselect(key="table_statuses").set_value(["Pending"]).run()
        self.assert_counts(app, rows)
        self.assertEqual(len(app.dataframe[-1].value), 25)
        pending_id = rows.loc[rows["Status"].eq("Pending"), "PA_Request_ID"].iloc[0]
        app.text_input(key="request_id").set_value(pending_id.lower()).run()
        self.assert_counts(app, rows)
        self.assertEqual(len(app.dataframe[-1].value), 1)
        app.sidebar.button[0].click().run()
        self.assert_counts(app, rows)
        self.assertEqual(len(app.dataframe[-1].value), 25)
        self.assertEqual(app.multiselect(key="table_statuses").value, [])
        self.assertEqual(app.text_input(key="request_id").value, "")

    def test_month_filters_and_supported_comparison(self):
        app = self.make_app()
        rows = load_requests()
        app.radio(key="period_mode").set_value("Month").run()
        app.selectbox(key="month").set_value("2026-02").run()
        expected = rows.loc[rows["Received_Date"].between("2026-02-01", "2026-02-28")]
        self.assert_counts(app, expected)
        self.assertFalse(app.checkbox(key="compare").disabled)
        self.assertEqual(
            app.sidebar.checkbox(key="compare").label, "Compare with previous month"
        )
        app.checkbox(key="compare").check().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.dataframe), 2)
        previous = rows.loc[rows["Received_Date"].between("2026-01-01", "2026-01-31")]
        self.assertTrue(app.dataframe[0].value.equals(comparison_table(expected, previous)))
        app.multiselect(key="categories").set_value(["Cardiology"]).run()
        app.multiselect(key="request_types").set_value(["Expedited"]).run()
        expected = expected.loc[
            expected["Procedure_Category"].eq("Cardiology")
            & expected["Request_Type"].eq("Expedited")
        ]
        self.assert_counts(app, expected)
        self.assertEqual(len(app.dataframe[-1].value), len(expected))
        app.sidebar.button[0].click().run()
        self.assert_counts(app, rows)
        self.assertEqual(app.radio(key="period_mode").value, "All available data")
        self.assertEqual(len(app.checkbox), 0)
        self.assertFalse(app.session_state["compare"])
        self.assertEqual(app.multiselect(key="categories").value, [])
        self.assertEqual(app.multiselect(key="request_types").value, [])
        # A subsequent browser rerun must not revive the old reporting scope.
        app.multiselect(key="table_statuses").set_value(["Pending"]).run()
        self.assert_counts(app, rows)
        self.assertEqual(len(app.dataframe[-1].value), 25)

    def test_pagination_search_and_reset_leave_summary_unchanged(self):
        app = self.make_app()
        rows = load_requests()
        self.assertTrue(app.dataframe[-1].value.equals(rows.iloc[:25]))
        self.assertTrue(app.button(key="previous_page").disabled)
        app.button(key="next_page").click().run()
        self.assertEqual(app.number_input(key="request_page").value, 2)
        self.assertTrue(app.dataframe[-1].value.equals(rows.iloc[25:50]))
        self.assert_counts(app, rows)
        app.number_input(key="request_page").set_value(20).run()
        self.assertTrue(app.dataframe[-1].value.equals(rows.iloc[475:500]))
        self.assertTrue(app.button(key="next_page").disabled)
        app.selectbox(key="request_page_size").set_value(100).run()
        self.assertEqual(app.number_input(key="request_page").value, 1)
        self.assertEqual(len(app.dataframe[-1].value), 100)
        app.text_input(key="request_id").set_value(rows.iloc[0]["PA_Request_ID"]).run()
        self.assertEqual(len(app.dataframe[-1].value), 1)
        self.assertEqual(app.number_input(key="request_page").value, 1)
        self.assert_counts(app, rows)
        app.text_input(key="request_id").set_value("NO-MATCH").run()
        self.assertTrue(app.dataframe[-1].value.empty)
        self.assertTrue(app.button(key="next_page").disabled)
        app.sidebar.button[0].click().run()
        self.assertEqual(app.number_input(key="request_page").value, 1)
        self.assertEqual(len(app.dataframe[-1].value), 100)
        self.assert_counts(app, rows)

    def test_quarter_year_custom_empty_and_invalid_dates(self):
        app = self.make_app()
        rows = load_requests()
        app.radio(key="period_mode").set_value("Quarter").run()
        app.selectbox(key="quarter").set_value("2026Q2").run()
        self.assert_counts(
            app, rows.loc[rows["Received_Date"].between("2026-04-01", "2026-06-30")]
        )
        self.assertEqual(
            app.sidebar.checkbox(key="compare").label, "Compare with previous quarter"
        )
        app.radio(key="period_mode").set_value("Year").run()
        app.selectbox(key="year").set_value(2026).run()
        self.assert_counts(app, rows.loc[rows["Received_Date"].str.startswith("2026")])
        self.assertEqual(len(app.checkbox), 0)
        app.radio(key="period_mode").set_value("Custom").run()
        app.date_input(key="start_date").set_value(date(2026, 2, 10)).run()
        app.date_input(key="end_date").set_value(date(2026, 2, 20)).run()
        self.assert_counts(
            app, rows.loc[rows["Received_Date"].between("2026-02-10", "2026-02-20")]
        )
        self.assertFalse(app.checkbox(key="compare").disabled)
        self.assertEqual(
            app.sidebar.checkbox(key="compare").label,
            "Compare with the previous period of the same length.",
        )
        app.checkbox(key="compare").check().run()
        self.assertEqual(len(app.dataframe), 2)
        app.date_input(key="start_date").set_value(date(2024, 1, 1)).run()
        app.date_input(key="end_date").set_value(date(2024, 12, 31)).run()
        self.assert_counts(app, rows.iloc[:0])
        self.assertEqual(len(app.checkbox), 0)
        self.assertFalse(app.session_state["compare"])
        self.assertEqual(len(app.dataframe[-1].value), 0)
        app.date_input(key="start_date").set_value(date(2025, 1, 1)).run()
        self.assertTrue(any("Start date" in error.value for error in app.error))
        app.sidebar.button[0].click().run()
        self.assert_counts(app, rows)

    def test_comparison_requires_previous_records_in_filtered_scope(self):
        rows = load_requests()
        candidate = None
        for row in rows.itertuples():
            day = date.fromisoformat(row.Received_Date)
            previous_day = day - timedelta(days=1)
            if previous_day.isoformat() < rows["Received_Date"].min():
                continue
            previous_rows = rows.loc[rows["Received_Date"].eq(previous_day.isoformat())]
            matching = previous_rows.loc[
                previous_rows["Procedure_Category"].eq(row.Procedure_Category)
                & previous_rows["Request_Type"].eq(row.Request_Type)
            ]
            if not previous_rows.empty and matching.empty:
                candidate = row, day
                break
        self.assertIsNotNone(candidate, "CSV must supply a filtered comparison edge case.")
        row, day = candidate
        app = self.make_app()
        app.radio(key="period_mode").set_value("Custom").run()
        app.date_input(key="start_date").set_value(day).run()
        app.date_input(key="end_date").set_value(day).run()
        app.sidebar.checkbox(key="compare").check().run()
        self.assertEqual(len(app.dataframe), 2)
        app.multiselect(key="categories").set_value([row.Procedure_Category]).run()
        app.multiselect(key="request_types").set_value([row.Request_Type]).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.checkbox), 0)
        self.assertFalse(app.session_state["compare"])
        self.assertEqual(len(app.dataframe), 1)
        app.multiselect(key="categories").set_value([]).run()
        app.multiselect(key="request_types").set_value([]).run()
        self.assertFalse(app.sidebar.checkbox(key="compare").value)


if __name__ == "__main__":
    unittest.main()
