"""Mocked routing: no API calls, no edits to the supplied CSV or saved database."""

import os
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage
from streamlit.testing.v1 import AppTest

from src.assistant_flow import answer_question, configured_model
from src.assistant_tools import make_tools
from src.data_loader import load_requests
from src.priority_metrics import category_summary, highest_pending_rate, largest_pending_workload
from src.reporting import calendar_period, filter_period, filter_scope, status_summary
from src.snapshot_store import SnapshotStore


APP = Path(__file__).resolve().parents[1] / "app.py"


class FakeModel:
    def __init__(self, name="status_totals", args=None):
        self.name, self.args = name, args or {}
        self.messages = []
        self.tools = []

    def bind_tools(self, tools, **kwargs):
        self.tools = tools
        assert kwargs == {"tool_choice": "required", "parallel_tool_calls": False}
        return self

    def invoke(self, messages):
        self.messages = messages
        return AIMessage(content="", tool_calls=[{"name": self.name, "args": self.args, "id": "test"}])


class AssistantTests(TestCase):
    def setUp(self):
        self.data = load_requests()

    def test_totals_and_denominators_match_existing_app(self):
        result = answer_question("What are the status totals?", self.data, FakeModel())
        self.assertEqual(result["status"], "answered")
        rows = result["evidence"]["rows"]
        self.assertEqual([row["Count"] for row in rows], [500, 35, 402, 63])
        for row, rate in zip(rows, (100, 7, 80.4, 12.6)):
            self.assertAlmostEqual(row["Rate"], rate)
        self.assertTrue(all(row["Denominator"] == 500 for row in rows))
        self.assertIn("not a quality score", result["answer"])

    def test_category_values_and_distinct_exact_leaders_match_priority_review(self):
        tools = make_tools(self.data)
        expected = category_summary(self.data)
        rows = tools["category_pending"].invoke({"view": "summary"})["rows"]
        self.assertEqual([row["Pending"] for row in rows], expected.Pending.tolist())
        self.assertEqual([row["Total requests"] for row in rows], expected.Total_Requests.tolist())
        self.assertEqual([row["Pending rate"] for row in rows], expected.Pending_Rate.tolist())
        for view, calculation in (
            ("largest_pending_count", largest_pending_workload),
            ("highest_pending_rate", highest_pending_rate),
        ):
            result = answer_question("Which category has the most Pending?", self.data, FakeModel("category_pending", {"view": view}))
            self.assertEqual([row["Category"] for row in result["evidence"]["rows"]],
                             calculation(expected).Procedure_Category.tolist())
        self.assertNotEqual(largest_pending_workload(expected).iloc[0].Procedure_Category,
                            highest_pending_rate(expected).iloc[0].Procedure_Category)

    def test_period_category_and_request_type_scope_are_respected(self):
        scope = filter_period(
            filter_scope(self.data, ["Advanced Imaging"], ["Standard"]),
            calendar_period("Month", "2026-08"),
        )
        result = answer_question("How many Pending requests?", scope, FakeModel())
        self.assertEqual(result["evidence"]["rows"][0]["Count"], len(scope))
        self.assertEqual(result["evidence"]["rows"][1]["Count"], status_summary(scope)["counts"]["Pending"])

    def test_one_category_is_case_insensitive(self):
        result = answer_question("What is the Pending rate for Cardiology?", self.data,
                                 FakeModel("category_pending", {"view": "summary", "category": "cardiology"}))
        self.assertEqual(len(result["evidence"]["rows"]), 1)
        self.assertEqual(result["evidence"]["rows"][0]["Category"], "Cardiology")

    def test_empty_scope_and_absent_category(self):
        for name, args in (("status_totals", {}), ("category_pending", {"view": "summary"})):
            result = answer_question("How many Pending requests?", self.data.iloc[0:0], FakeModel(name, args))
            self.assertEqual(result["status"], "no_results")
        result = answer_question("What is the Pending rate?", self.data,
                                 FakeModel("category_pending", {"view": "summary", "category": "not available"}))
        self.assertEqual(result["status"], "no_results")

    def test_empty_question_missing_key_and_no_client_created(self):
        self.assertEqual(answer_question(" ", self.data, FakeModel())["status"], "empty")
        self.assertEqual(answer_question("Pending count?", self.data, None)["status"], "setup")
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}), patch("src.assistant_flow.ChatOpenAI") as client:
            self.assertIsNone(configured_model())
            client.assert_not_called()

    def test_model_configuration_and_output_bound_without_api_call(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "mock-only", "OPENAI_MODEL": "gpt-4.1-mini"}):
            model = configured_model()  # Constructing a client does not send a request.
        self.assertEqual(model.model_name, "gpt-4.1-mini")
        self.assertEqual(model.max_tokens, 256)
        self.assertEqual(model.max_retries, 0)

    def test_unsafe_questions_are_declined_without_a_model_call(self):
        for question in ("Why are requests denied?", "Rank employees", "Clinical advice",
                         "Look up SYNPA0001", "Execute SQL", "Recommend approvals"):
            model = FakeModel()
            result = answer_question(question, self.data, model)
            self.assertEqual(result["status"], "unsupported")
            self.assertEqual(model.messages, [])

    def test_other_unsupported_and_outside_scope_questions(self):
        for reason in ("unavailable_calculation", "outside_scope"):
            result = answer_question("Compare month-end trends", self.data,
                                     FakeModel("report_limitation", {"reason": reason}))
            self.assertEqual(result["status"], "unsupported")
            self.assertEqual(result["evidence"]["rows"], [])

    def test_bad_tools_extra_arguments_and_model_errors_fail_closed(self):
        for model in (
            FakeModel("run_python", {"code": "anything"}),
            FakeModel("status_totals", {"sql": "anything"}),
            FakeModel("category_pending", {"view": "unsupported"}),
        ):
            self.assertEqual(answer_question("Show totals", self.data, model)["status"], "error")
        model = FakeModel()
        model.invoke = Mock(side_effect=RuntimeError("sensitive provider details"))
        result = answer_question("Show totals", self.data, model)
        self.assertEqual(result["status"], "error")
        self.assertNotIn("sensitive provider", result["answer"])
        self.assertIsNone(result["evidence"])

    def test_multiple_tool_calls_are_rejected(self):
        model = FakeModel()
        model.invoke = Mock(return_value=AIMessage(content="", tool_calls=[
            {"name": "status_totals", "args": {}, "id": "one"},
            {"name": "status_totals", "args": {}, "id": "two"},
        ]))
        self.assertEqual(answer_question("Show totals", self.data, model)["status"], "error")

    def test_model_only_receives_question_and_tool_schemas(self):
        model = FakeModel("category_pending", {"view": "highest_pending_rate"})
        answer_question("Which category has the highest Pending rate?", self.data, model)
        self.assertEqual(len(model.messages), 2)
        text = " ".join(message.content for message in model.messages)
        self.assertNotIn("SYNPA0001", text)
        self.assertNotIn("Received_Date", text)
        self.assertNotIn("500", text)
        self.assertEqual({tool.name for tool in model.tools},
                         {"status_totals", "category_pending", "report_limitation"})

    def test_check_node_rejects_tampered_evidence(self):
        tool = Mock()
        tool.invoke.side_effect = [
            {"kind": "status_totals", "rows": [{"Count": 999}]},
            {"kind": "status_totals", "rows": [{"Count": 500}]},
        ]
        with patch("src.assistant_flow.make_tools", return_value={"status_totals": tool}):
            result = answer_question("Show totals", self.data, FakeModel())
        self.assertEqual(result["status"], "error")
        self.assertIsNone(result["evidence"])


class AssistantScreenTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.patch_db = patch("src.snapshot_store.DEFAULT_DB_PATH", Path(self.tmp.name) / "snapshots.sqlite3")
        self.patch_db.start()
        self.addCleanup(self.patch_db.stop)

    def app(self):
        return AppTest.from_file(str(APP), default_timeout=30).run()

    def test_missing_key_setup_and_navigation(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            app = self.app()
            app.radio(key="screen").set_value("Ask the Data").run()
            self.assertFalse(app.exception)
            self.assertTrue(app.button(key="ask_submit").disabled)
            self.assertTrue(any("OPENAI_API_KEY" in item.value for item in app.caption))
            self.assertFalse(any("not connected" in item.value.lower() for item in app.info))
            self.assertTrue(any("Not recorded" in item.value for item in app.markdown))
            self.assertTrue(any("Requests received (Received_Date)" in item.value for item in app.markdown))
            self.assertTrue(any("Example questions" in item.value for item in app.markdown))
            self.assertTrue(any(
                item.value == "Synthetic data only—do not enter member, clinical, or request details."
                for item in app.caption
            ))
            self.assertFalse(any("Ask about recorded status totals" in item.value for item in app.caption))
            self.assertFalse(any(
                "Displayed statuses come from the selected snapshot" in item.value
                for item in app.caption
            ))
            sidebar_captions = " ".join(item.value for item in app.sidebar.caption)
            self.assertNotIn("These selections update the summary and request list.", sidebar_captions)
            self.assertNotIn(
                "Reporting periods use Received_Date; statuses come from the selected snapshot.",
                sidebar_captions,
            )
            self.assertNotIn(
                "A previous-period comparison is unavailable because this file contains no earlier received-date period.",
                sidebar_captions,
            )
            self.assertFalse(app.file_uploader)
            app.radio(key="screen").set_value("Priority Review").run()
            self.assertFalse(app.exception)
            self.assertTrue(any("Largest Pending Workload" == item.value for item in app.subheader))

    def test_present_key_enables_question_without_disconnected_warning(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "mock-only"}), \
             patch("src.ask_data_page.configured_model", return_value=FakeModel()):
            app = self.app()
            app.radio(key="screen").set_value("Ask the Data").run()
        self.assertFalse(app.exception)
        self.assertFalse(app.button(key="ask_submit").disabled)
        self.assertFalse(any("OPENAI_API_KEY" in item.value for item in app.caption))
        self.assertFalse(any("not connected" in item.value.lower() for item in app.info))
        self.assertFalse(any("not connected" in item.value.lower() for item in app.caption))
        self.assertTrue(any(
            item.value == "Synthetic data only—do not enter member, clinical, or request details."
            for item in app.caption
        ))

    def test_mocked_answer_scope_invalidation_and_ignored_table_filters(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "mock-only"}), \
             patch("src.ask_data_page.configured_model", return_value=FakeModel()):
            app = self.app()
            app.multiselect(key="table_statuses").set_value(["Denied"]).run()
            app.text_input(key="request_id").set_value("DOES_NOT_MATCH").run()
            app.radio(key="screen").set_value("Ask the Data").run()
            app.text_area[0].set_value("Show status totals")
            app.button(key="ask_submit").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.dataframe[0].value.Count.tolist(), [500, 35, 402, 63])
            self.assertTrue(any("Status snapshot date: Not recorded" in item.value for item in app.caption))
            app.radio(key="period_mode").set_value("Month").run()
            self.assertFalse(app.exception)
            self.assertFalse(app.dataframe)  # stale answer removed immediately
            app.text_area[0].set_value("How many Pending requests?")
            app.button(key="ask_submit").click().run()
            expected = filter_period(load_requests(), calendar_period("Month", app.selectbox(key="month").value))
            self.assertEqual(app.dataframe[0].value.iloc[0].Count, len(expected))

    def test_saved_snapshot_selection_used_by_answer(self):
        data = load_requests().copy()
        data.loc[data.index[0], "Status"] = "Pending"
        SnapshotStore().save_upload(
            "test.csv", data.to_csv(index=False).encode(), date(2026, 10, 8),
            synthetic_confirmed=True,
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "mock-only"}), \
             patch("src.ask_data_page.configured_model", return_value=FakeModel()):
            app = self.app()
            app.radio(key="screen").set_value("Ask the Data").run()
            app.text_area[0].set_value("Show status totals")
            app.button(key="ask_submit").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.dataframe[0].value.iloc[1].Count, status_summary(data)["counts"]["Pending"])
            self.assertTrue(any("October 8, 2026" in item.value for item in app.caption))
            app.selectbox(key="selected_snapshot").set_value("original").run()
            self.assertFalse(app.dataframe)
