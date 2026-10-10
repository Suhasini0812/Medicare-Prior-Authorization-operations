"""Fast checks of reporting math using the original supplied CSV."""

import unittest
from datetime import date

import pandas as pd

from src.data_loader import load_requests
from src.reporting import (
    ReportingPeriod, calendar_period, comparison_availability, comparison_table,
    filter_period, filter_scope, filter_table, previous_period, status_summary,
)


class ReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.requests = load_requests()
        cls.coverage = (date(2025, 10, 1), date(2026, 9, 29))

    def test_original_totals_and_percentages(self):
        result = status_summary(self.requests)
        self.assertEqual(result["total"], 500)
        self.assertEqual(result["counts"], {"Approved": 402, "Denied": 63, "Pending": 35})
        for status, percentage in {"Approved": 80.4, "Denied": 12.6, "Pending": 7.0}.items():
            self.assertAlmostEqual(result["percentages"][status], percentage)

    def test_calendar_and_previous_bounds(self):
        cases = [
            ("Month", "2026-02", date(2026, 2, 1), date(2026, 2, 28),
             date(2026, 1, 1), date(2026, 1, 31)),
            ("Quarter", "2026Q2", date(2026, 4, 1), date(2026, 6, 30),
             date(2026, 1, 1), date(2026, 3, 31)),
            ("Year", "2026", date(2026, 1, 1), date(2026, 12, 31),
             date(2025, 1, 1), date(2025, 12, 31)),
        ]
        for mode, value, start, end, prev_start, prev_end in cases:
            with self.subTest(mode=mode):
                period = calendar_period(mode, value)
                self.assertEqual((period.start, period.end), (start, end))
                previous = previous_period(period)
                self.assertEqual((previous.start, previous.end), (prev_start, prev_end))

    def test_custom_equivalent_period(self):
        period = ReportingPeriod("Custom", date(2026, 3, 10), date(2026, 3, 20))
        previous = previous_period(period)
        self.assertEqual(previous.start, date(2026, 2, 27))
        self.assertEqual(previous.end, date(2026, 3, 9))

    def test_scope_and_inclusive_period_filters(self):
        period = ReportingPeriod("Custom", date(2026, 1, 1), date(2026, 3, 31))
        actual = filter_period(
            filter_scope(self.requests, ["Cardiology"], ["Expedited"]), period
        )
        expected = self.requests.loc[
            self.requests["Procedure_Category"].eq("Cardiology")
            & self.requests["Request_Type"].eq("Expedited")
            & self.requests["Received_Date"].between("2026-01-01", "2026-03-31")
        ]
        pd.testing.assert_frame_equal(actual, expected)

    def test_table_filters_do_not_change_summary(self):
        original = status_summary(self.requests)
        pending = filter_table(self.requests, ["Pending"], "")
        self.assertEqual(len(pending), 35)
        self.assertEqual(status_summary(self.requests), original)
        result = filter_table(self.requests, [], "synpa0001")
        self.assertEqual(result["PA_Request_ID"].tolist(), ["SYNPA0001"])
        self.assertTrue(filter_table(self.requests, [], "[").empty)

    def test_comparisons_do_not_infer_coverage_or_completeness(self):
        self.assertTrue(comparison_availability(
            self.requests, calendar_period("Month", "2026-02"), self.coverage
        )[0])
        for period in (
            calendar_period("Month", "2025-10"),
            calendar_period("Month", "2026-09"),
            calendar_period("Year", "2026"),
        ):
            self.assertFalse(comparison_availability(self.requests, period, self.coverage)[0])
        empty = self.requests.iloc[:0]
        self.assertFalse(comparison_availability(
            empty, calendar_period("Month", "2026-02"), self.coverage
        )[0])

    def test_empty_cohort_has_no_fabricated_percentage(self):
        result = status_summary(self.requests.iloc[:0])
        self.assertEqual(result["total"], 0)
        self.assertTrue(all(value is None for value in result["percentages"].values()))

    def test_comparison_denominators_and_source_preserved(self):
        original = self.requests.copy(deep=True)
        period = calendar_period("Month", "2026-02")
        current = filter_period(self.requests, period)
        previous = filter_period(self.requests, previous_period(period))
        comparison = comparison_table(current, previous)
        self.assertEqual(comparison.iloc[0]["Selected count"], len(current))
        self.assertEqual(comparison.iloc[0]["Previous count"], len(previous))
        self.assertIn(f"/{len(current)})", comparison.iloc[1]["Selected share / denominator"])
        pd.testing.assert_frame_equal(self.requests, original)


if __name__ == "__main__":
    unittest.main()
