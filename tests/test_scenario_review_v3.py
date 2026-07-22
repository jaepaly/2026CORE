import csv
import json
import tempfile
import unittest
from pathlib import Path

from scenario_review_v3 import export_review_csv, select_approved_scenarios


class ScenarioReviewV3Tests(unittest.TestCase):
    def test_export_marks_legacy_scenarios_pending_without_inventing_v3_labels(self):
        legacy = {
            "scenarios": [
                {
                    "id": "s1",
                    "name": "회의 일정 조율",
                    "task": "김민수와 회의 일정 조율",
                    "minimum": ["c1", "e5", "cal2"],
                    "success_criteria": {"output_format": "회의 일정"},
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            csv_path = Path(temporary_directory) / "scenario_review.csv"

            export_review_csv(legacy, csv_path)

            with csv_path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(1, len(rows))
        self.assertEqual("v3_s1", rows[0]["scenario_id"])
        self.assertEqual("pending", rows[0]["review_status"])
        self.assertEqual(json.dumps(["c1", "e5", "cal2"], ensure_ascii=False), rows[0]["legacy_minimum_ids"])
        self.assertEqual("", rows[0]["required_record_paths"])
        self.assertEqual("", rows[0]["allowed_field_paths"])
        self.assertEqual("", rows[0]["reviewer_1"])

    def test_pending_review_row_cannot_enter_main_experiment(self):
        pending = {
            "scenario_id": "v3_s1",
            "review_status": "pending",
            "required_record_paths": "[\"contacts/c1\"]",
            "allowed_field_paths": "[\"contacts/name\"]",
            "reviewer_1": "reviewer-a",
            "reviewer_2": "reviewer-b",
        }

        with self.assertRaisesRegex(ValueError, "not approved"):
            select_approved_scenarios([pending])

    def test_approved_row_requires_two_reviewers_and_access_labels(self):
        incomplete = {"scenario_id": "v3_s1", "review_status": "approved"}

        with self.assertRaisesRegex(ValueError, "missing review fields"):
            select_approved_scenarios([incomplete])


if __name__ == "__main__":
    unittest.main()
