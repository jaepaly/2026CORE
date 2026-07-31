import json
import tempfile
import unittest
from pathlib import Path

from run_model_pilot_v3 import judge, probe_model, write_report

GATE = {"min_valid_tool_call_rate": 0.8, "max_server_or_parser_error_rate": 0.05}
TASKS = ["과제 1", "과제 2", "과제 3", "과제 4", "과제 5"]


def step_returning(sequence):
    responses = iter(sequence)

    def model_step(messages):
        item = next(responses)
        if isinstance(item, Exception):
            raise item
        return item
    return model_step


TOOL_CALL = {"content": "", "tool_calls": [{"name": "search_contacts", "arguments": {}}]}
NO_CALL = {"content": "검색하겠습니다.", "tool_calls": []}


class ProbeTests(unittest.TestCase):
    def test_counts_tool_calls_and_errors(self):
        result = probe_model(
            model_step=step_returning([TOOL_CALL, TOOL_CALL, NO_CALL,
                                       ConnectionError("down"), TOOL_CALL]),
            tasks=TASKS, system_prompt="중립",
        )

        self.assertEqual(5, result["probes"])
        self.assertAlmostEqual(0.6, result["valid_tool_call_rate"])
        self.assertAlmostEqual(0.2, result["error_rate"])

    def test_narrating_instead_of_calling_is_not_a_tool_call(self):
        """v2's trap: 'I will search' reads as zero access, not as privacy."""
        result = probe_model(model_step=step_returning([NO_CALL] * 5),
                             tasks=TASKS, system_prompt="중립")

        self.assertEqual(0.0, result["valid_tool_call_rate"])
        self.assertEqual(0.0, result["error_rate"])

    def test_malformed_tool_call_entries_do_not_count(self):
        result = probe_model(
            model_step=step_returning([{"content": "", "tool_calls": [{"arguments": {}}]}] * 5),
            tasks=TASKS, system_prompt="중립",
        )

        self.assertEqual(0.0, result["valid_tool_call_rate"])


class GateTests(unittest.TestCase):
    def test_model_at_the_threshold_is_included(self):
        included, reasons = judge({"valid_tool_call_rate": 0.8, "error_rate": 0.05}, GATE)

        self.assertTrue(included)
        self.assertEqual([], reasons)

    def test_low_tool_call_rate_is_excluded(self):
        included, reasons = judge({"valid_tool_call_rate": 0.12, "error_rate": 0.0}, GATE)

        self.assertFalse(included)
        self.assertIn("valid tool-call rate", reasons[0])

    def test_high_error_rate_is_excluded(self):
        included, reasons = judge({"valid_tool_call_rate": 1.0, "error_rate": 0.4}, GATE)

        self.assertFalse(included)
        self.assertIn("error rate", reasons[0])


class ReportTests(unittest.TestCase):
    def test_report_records_inclusions_and_exclusions_with_numbers(self):
        results = {
            "good:8b": {"probes": 10, "valid_tool_call_rate": 1.0, "error_rate": 0.0,
                        "included": True, "reasons": []},
            "silent:7b": {"probes": 10, "valid_tool_call_rate": 0.0, "error_rate": 0.0,
                          "included": False, "reasons": ["valid tool-call rate 0% < 80%"]},
        }
        with tempfile.TemporaryDirectory() as directory:
            write_report(Path(directory), GATE, results)
            report = (Path(directory) / "model_inclusion.md").read_text(encoding="utf-8")
            raw = json.loads((Path(directory) / "model_pilot.json").read_text(encoding="utf-8"))

        self.assertIn("silent:7b", report)
        self.assertIn("제외", report)
        self.assertIn("good:8b", report)
        self.assertEqual(GATE, raw["gate"])


if __name__ == "__main__":
    unittest.main()
