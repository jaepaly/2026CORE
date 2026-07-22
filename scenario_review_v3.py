"""Human-review export for v3 scenario labels.

The exporter deliberately preserves legacy hints only as review context. It does
not infer required fields, permitted fields, or task success labels.
"""

import csv
import json
from pathlib import Path

from validation_v3 import validate_success_validator


REVIEW_COLUMNS = [
    "scenario_id",
    "name",
    "task",
    "legacy_minimum_ids",
    "legacy_success_criteria",
    "required_record_paths",
    "allowed_field_paths",
    "forbidden_sensitive_field_paths",
    "success_validator",
    "reviewer_1",
    "reviewer_2",
    "adjudicator",
    "review_status",
    "review_notes",
]


def export_review_csv(legacy: dict, csv_path: str | Path) -> None:
    rows = []
    for scenario in legacy.get("scenarios", []):
        rows.append(
            {
                "scenario_id": f"v3_{scenario['id']}",
                "name": scenario.get("name", ""),
                "task": scenario.get("task", ""),
                "legacy_minimum_ids": json.dumps(scenario.get("minimum", []), ensure_ascii=False),
                "legacy_success_criteria": json.dumps(
                    scenario.get("success_criteria", {}), ensure_ascii=False, sort_keys=True
                ),
                "required_record_paths": "",
                "allowed_field_paths": "",
                "forbidden_sensitive_field_paths": "",
                "success_validator": "",
                "reviewer_1": "",
                "reviewer_2": "",
                "adjudicator": "",
                "review_status": "pending",
                "review_notes": "",
            }
        )
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def select_approved_scenarios(rows: list[dict]) -> list[dict]:
    required_review_fields = {
        "required_record_paths",
        "allowed_field_paths",
        "success_validator",
        "reviewer_1",
        "reviewer_2",
    }
    for row in rows:
        if row.get("review_status") != "approved":
            raise ValueError(f"scenario {row.get('scenario_id', '')} is not approved")
        missing = sorted(field for field in required_review_fields if not row.get(field))
        if missing:
            raise ValueError(f"missing review fields: {', '.join(missing)}")
        try:
            validator = json.loads(row["success_validator"])
            validate_success_validator(validator)
        except (json.JSONDecodeError, ValueError) as error:
            raise ValueError("structured success validator is required") from error
    return rows
