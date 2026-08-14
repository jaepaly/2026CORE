import csv
import json
import unittest
from pathlib import Path

from policy_lint_v3 import (
    ToolGraph,
    has_errors,
    lint_policy,
    workspace_tool_graph,
)

ROOT = Path(__file__).resolve().parents[1]


def codes(diagnostics) -> set[str]:
    return {d.code for d in diagnostics}


def simple_graph() -> ToolGraph:
    return (ToolGraph()
            .add("search_people", ["id", "name", "email"])
            .add("get_person", ["id", "name", "email", "phone"], discovery_tool="search_people")
            .add("create_note", [], writes=True))


class UnknownFieldTests(unittest.TestCase):
    def test_field_the_tool_cannot_return_is_an_error(self):
        found = lint_policy({"get_person": ["id", "ssn"]}, simple_graph())

        self.assertIn("P1", codes(found))
        self.assertTrue(has_errors(found))

    def test_unknown_tool_is_an_error(self):
        found = lint_policy({"get_invoice": ["id"]}, simple_graph())

        self.assertIn("P1", codes(found))

    def test_known_fields_do_not_raise_P1(self):
        found = lint_policy(
            {"search_people": ["id"], "get_person": ["id", "phone"]}, simple_graph())

        self.assertNotIn("P1", codes(found))


class ReachabilityTests(unittest.TestCase):
    def test_detail_tool_without_a_discovery_identifier_is_unreachable(self):
        """A permission the agent can never exercise looks generous and gives nothing."""
        found = lint_policy({"get_person": ["id", "name"]}, simple_graph())

        self.assertIn("P2", codes(found))
        self.assertTrue(has_errors(found))

    def test_granting_the_discovery_identifier_makes_it_reachable(self):
        found = lint_policy(
            {"search_people": ["id", "name"], "get_person": ["id", "phone"]}, simple_graph())

        self.assertNotIn("P2", codes(found))
        self.assertFalse(has_errors(found))

    def test_discovery_identifier_must_be_the_identifier_not_just_any_field(self):
        found = lint_policy(
            {"search_people": ["name"], "get_person": ["phone"]}, simple_graph())

        self.assertIn("P2", codes(found))


class WarningTests(unittest.TestCase):
    def test_search_tool_without_identifier_warns_but_is_not_an_error(self):
        found = lint_policy({"search_people": ["name", "email"]}, simple_graph())

        self.assertIn("P3", codes(found))
        self.assertFalse(has_errors(found))

    def test_empty_policy_warns(self):
        found = lint_policy({}, simple_graph())

        self.assertEqual({"P4"}, codes(found))
        self.assertFalse(has_errors(found))

    def test_write_tool_is_exempt_from_identifier_rules(self):
        """create_note returns no records, so there is no id to grant."""
        found = lint_policy(
            {"search_people": ["id"], "create_note": []}, simple_graph())

        self.assertEqual(set(), codes(found))


class InputShapeTests(unittest.TestCase):
    def test_flat_path_list_is_accepted(self):
        found = lint_policy(["search_people.id", "get_person.phone"], simple_graph())

        self.assertFalse(has_errors(found))

    def test_fully_qualified_paths_inside_the_mapping_are_accepted(self):
        found = lint_policy(
            {"search_people": ["search_people.id"], "get_person": ["get_person.phone"]},
            simple_graph())

        self.assertFalse(has_errors(found))

    def test_a_bare_string_value_is_treated_as_one_field(self):
        found = lint_policy({"search_people": "id"}, simple_graph())

        self.assertFalse(has_errors(found))


class WorkspaceGraphTests(unittest.TestCase):
    def test_graph_is_built_from_the_fixtures(self):
        graph = workspace_tool_graph()

        self.assertEqual("search_contacts", graph.tools["get_contact"].discovery_tool)
        self.assertEqual("search_emails", graph.tools["get_email"].discovery_tool)
        self.assertIsNone(graph.tools["search_calendar"].discovery_tool)
        self.assertTrue(graph.tools["create_event"].writes)

    def test_every_reviewed_policy_passes(self):
        """The reviewed labels are the standard the check is meant to approach.

        If any of them were rejected, the rules would be encoding this study's
        labelling convention rather than whether a policy can execute -- and the
        evaluation in evaluate_policy_lint_v3 would be measuring itself.
        """
        graph = workspace_tool_graph()
        review_csv = ROOT / "data" / "scenario_review_v3.csv"
        with review_csv.open(encoding="utf-8", newline="") as handle:
            approved = [r for r in csv.DictReader(handle)
                        if (r.get("review_status") or "").strip() == "approved"]
        self.assertTrue(approved)

        offenders = {}
        for row in approved:
            found = lint_policy(json.loads(row["allowed_field_paths"]), graph)
            if found:
                offenders[row["scenario_id"]] = [str(d) for d in found]

        self.assertEqual({}, offenders)


if __name__ == "__main__":
    unittest.main()
