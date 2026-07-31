import unittest

from tools_v3 import TOOLS_SCHEMA, WorkspaceTools
from prompt_v3 import DEFAULT_TOOL_NAMES


class ToolSchemaTests(unittest.TestCase):
    def test_schema_names_match_the_prompt_tool_inventory(self):
        """Labels, prompt and schema must speak of the same tools."""
        schema_names = {entry["function"]["name"] for entry in TOOLS_SCHEMA}

        self.assertEqual(set(DEFAULT_TOOL_NAMES), schema_names)

    def test_every_schema_tool_is_dispatchable(self):
        tools = WorkspaceTools()

        for name in (entry["function"]["name"] for entry in TOOLS_SCHEMA):
            with self.subTest(tool=name):
                self.assertTrue(callable(getattr(tools, name, None)))


class LosslessReadTests(unittest.TestCase):
    """Tools return whole records; only the policy layer removes fields."""

    def setUp(self):
        self.tools = WorkspaceTools()

    def test_search_contacts_returns_every_field_including_sensitive_ones(self):
        found = self.tools.search_contacts(query="김민수")

        self.assertTrue(found)
        self.assertIn("phone", found[0])
        self.assertIn("notes", found[0])

    def test_get_contact_and_search_contacts_agree_on_the_same_record(self):
        detail = self.tools.get_contact(id="c1")
        searched = [r for r in self.tools.search_contacts(query="김민수", limit=15)
                    if r["id"] == "c1"][0]

        self.assertEqual(detail, searched)

    def test_search_emails_returns_body(self):
        found = self.tools.search_emails(query="회의", limit=3)

        self.assertTrue(found)
        self.assertIn("body", found[0])

    def test_calendar_records_keep_their_nested_events(self):
        found = self.tools.search_calendar(date_from="2025-06-24", date_to="2025-06-24")

        self.assertTrue(found)
        self.assertIn("participants", found[0]["events"][0])


class FilterTests(unittest.TestCase):
    def setUp(self):
        self.tools = WorkspaceTools()

    def test_date_range_filters_emails(self):
        found = self.tools.search_emails(date_from="2025-06-21", date_to="2025-06-21", limit=50)

        self.assertTrue(found)
        for record in found:
            self.assertTrue(record["date"].startswith("2025-06-21"))

    def test_sender_filter(self):
        found = self.tools.search_emails(sender="minsu.kim@example.com", limit=50)

        self.assertTrue(found)
        for record in found:
            self.assertEqual("minsu.kim@example.com", record["from"])

    def test_limit_is_honoured(self):
        self.assertEqual(2, len(self.tools.search_emails(limit=2)))

    def test_results_are_ordered_deterministically(self):
        first = [r["id"] for r in self.tools.search_contacts(query="", limit=15)]
        second = [r["id"] for r in self.tools.search_contacts(query="", limit=15)]

        self.assertEqual(first, second)
        self.assertEqual(["c1", "c2", "c3"], first[:3])  # numeric, not lexicographic


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.tools = WorkspaceTools()

    def test_create_event_is_sandboxed_and_does_not_mutate_the_workspace(self):
        before = len(self.tools.calendar)

        result = self.tools.create_event(title="t", date="2025-07-01", time="10:00",
                                         participants=["me"])

        self.assertEqual("sandbox_created", result["status"])
        self.assertEqual(before, len(self.tools.calendar))

    def test_missing_record_reports_in_band(self):
        self.assertEqual({"error": "contact_not_found"}, self.tools.get_contact(id="c999"))

    def test_unknown_tool_reports_in_band(self):
        self.assertIn("unknown_tool", self.tools("drop_database", {})["error"])

    def test_private_attributes_are_not_dispatchable(self):
        self.assertIn("unknown_tool", self.tools("_load", {})["error"])

    def test_bad_arguments_do_not_raise(self):
        result = self.tools("get_contact", {"wrong_kwarg": 1})

        self.assertEqual("invalid_arguments", result["error"])


if __name__ == "__main__":
    unittest.main()
