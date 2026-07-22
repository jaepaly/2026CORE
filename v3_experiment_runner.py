"""Reviewed-scenario v3 smoke runner with value-free persisted artifacts."""

import csv
import hashlib
import json
from pathlib import Path

from protocol_v3 import initialize_manifest
from scenario_review_v3 import select_approved_scenarios
from v3_runner import run_agent_turns
from validation_v3 import validate_run_outcome


def _json_array(value: str, field: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError(f"{field} must be a JSON array") from error
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError(f"{field} must be a JSON array of strings")
    return parsed


def _tool_fields(paths: list[str], field: str) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for path in paths:
        if "." not in path:
            raise ValueError(f"{field} path must use tool.field notation: {path}")
        tool_name, field_name = path.split(".", 1)
        if not tool_name or not field_name or "." in field_name:
            raise ValueError(f"invalid {field} path: {path}")
        grouped.setdefault(tool_name, []).append(field_name)
    return grouped


def _sensitive_fields(paths: list[str]) -> dict[str, set[str]]:
    return {tool: set(fields) for tool, fields in _tool_fields(paths, "forbidden_sensitive_field_paths").items()}


def _output_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_approved_rows(review_csv: str | Path) -> list[dict]:
    with Path(review_csv).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return select_approved_scenarios(rows)


def run_reviewed_smoke(
    *,
    review_csv: str | Path,
    protocol_path: str | Path,
    experiment_dir: str | Path,
    model: dict,
    git_commit: str,
    conditions: list[str],
    seed: int,
    max_turns: int,
    model_step,
    tool_executor,
) -> list[dict]:
    """Run approved rows through an injected model/tool path; persist no raw payloads."""
    rows = _load_approved_rows(review_csv)
    if not rows:
        raise ValueError("no approved scenarios")
    for condition in conditions:
        if condition not in {"A", "B", "C", "D"}:
            raise ValueError(f"unknown v3 condition: {condition}")

    planned_runs = [
        {"model": model["name"], "scenario": row["scenario_id"], "condition": condition,
         "seed": seed, "retry_index": 0}
        for row in rows for condition in conditions
    ]
    experiment_dir = Path(experiment_dir)
    initialize_manifest(
        experiment_dir=experiment_dir, protocol_path=protocol_path, scenario_path=review_csv,
        git_commit=git_commit, models=[model], planned_runs=planned_runs,
    )
    traces_dir = experiment_dir / "traces"
    traces_dir.mkdir(exist_ok=True)
    run_summaries = []
    validation_events = []
    for row in rows:
        projection = _tool_fields(_json_array(row["allowed_field_paths"], "allowed_field_paths"), "allowed_field_paths")
        sensitive = _sensitive_fields(_json_array(row.get("forbidden_sensitive_field_paths", "[]"), "forbidden_sensitive_field_paths"))
        validator = json.loads(row["success_validator"])
        for condition in conditions:
            run_id = f"{model['name'].replace(':', '_')}_{row['scenario_id']}_{condition}_s{seed}"
            outcome = run_agent_turns(
                model_step=model_step, tool_executor=tool_executor,
                initial_messages=[{"role": "user", "content": row["task"]}], condition=condition,
                projection_by_tool=projection, sensitive_fields_by_tool=sensitive, run_id=run_id,
                model=model["name"], scenario=row["scenario_id"], seed=seed, max_turns=max_turns,
            )
            (traces_dir / f"{run_id}.json").write_text(
                json.dumps(outcome["delivery_events"], ensure_ascii=False, indent=2), encoding="utf-8"
            )
            validation = validate_run_outcome(outcome["status"], outcome["final_output"], validator)
            validation_event = {
                "run_id": run_id, "model": model["name"], "scenario": row["scenario_id"],
                "condition": condition, "seed": seed, "retry_index": 0,
                **validation,
            }
            validation_events.append(validation_event)
            summary = {
                "run_id": run_id, "model": model["name"], "scenario": row["scenario_id"],
                "condition": condition, "seed": seed, "retry_index": 0,
                "status": outcome["status"], "delivery_event_count": len(outcome["delivery_events"]),
                "final_output_sha256": _output_sha256(outcome["final_output"]),
                "final_output_char_count": len(outcome["final_output"]),
                **validation,
            }
            run_summaries.append(summary)
    (experiment_dir / "validation.json").write_text(
        json.dumps(validation_events, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (experiment_dir / "runs.jsonl").write_text(
        "".join(json.dumps(summary, ensure_ascii=False) + "\n" for summary in run_summaries), encoding="utf-8"
    )
    return run_summaries
