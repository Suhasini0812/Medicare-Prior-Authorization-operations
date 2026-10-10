"""Chart ranks and values must come directly from the category summary."""

import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from src.data_loader import load_requests
from src.priority_charts import build_category_chart
from src.priority_metrics import SUMMARY_COLUMNS, category_summary


class PriorityChartTests(unittest.TestCase):
    def test_independent_rankings_and_unrounded_values_match_the_table(self):
        summary = category_summary(load_requests())
        original = summary.copy(deep=True)
        for rate, metric in ((False, "Pending"), (True, "Pending_Rate")):
            with self.subTest(rate=rate):
                chart = build_category_chart(summary, rate=rate).to_dict()
                data = pd.DataFrame(chart["datasets"][chart["data"]["name"]])
                expected = summary.sort_values(
                    [metric, "Procedure_Category"], ascending=[False, True],
                ).reset_index(drop=True)
                assert_frame_equal(data[list(SUMMARY_COLUMNS)], expected)
                self.assertEqual(chart["encoding"]["y"]["sort"],
                                 expected["Procedure_Category"].tolist())
                self.assertEqual(chart["mark"]["type"], "bar")
                self.assertTrue(chart["encoding"]["x"]["scale"]["zero"])
                if rate:
                    self.assertEqual(expected.iloc[0]["Procedure_Category"], "Physical Therapy")
                    self.assertEqual(chart["encoding"]["x"]["axis"]["format"], ".1%")
                    self.assertAlmostEqual(data.iloc[0]["Pending_Share"], 0.09)
                else:
                    self.assertEqual(data["Pending"].tolist(), [17, 9, 5, 4])
                self.assertEqual(
                    [item["field"] for item in chart["encoding"]["tooltip"]],
                    ["Procedure_Category", "Pending", "Total_Requests", "Pending_Share"],
                )
        assert_frame_equal(summary, original)

    def test_zero_pending_and_empty_scopes_have_no_invalid_values(self):
        frame = pd.DataFrame({"Procedure_Category": ["A", "B"], "Status": ["Approved", "Denied"]})
        summary = category_summary(frame)
        for rate in (False, True):
            spec = build_category_chart(summary, rate=rate).to_dict()
            data = pd.DataFrame(spec["datasets"][spec["data"]["name"]])
            self.assertEqual(data["Pending_Share"].tolist(), [0, 0])
            empty = build_category_chart(category_summary(frame.iloc[:0]), rate=rate).to_dict()
            self.assertEqual(empty["datasets"][empty["data"]["name"]], [])


if __name__ == "__main__":
    unittest.main()
