#!/usr/bin/env python3
"""Run the pre-registered v3 controlled-disclosure study.

    python run_experiment_v3.py --experiment-dir experiments/main --model qwen3:8b
    python run_experiment_v3.py --experiment-dir experiments/main --model qwen3:8b --limit 3

Every completed run is appended to ``runs.jsonl`` immediately, and a rerun skips
tuples already present there.  The study is ~688 runs at roughly half a minute
each, so a crash partway through must not cost the whole batch -- and the team
splits the work by model, which is the same mechanism.

The manifest is frozen on first write.  Re-running with identical settings is
idempotent; re-running with different settings is refused rather than silently
overwriting the record of what earlier runs were executed under.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import requests

from delivery_audit_v3 import count_excess_sensitive_fields
from ollama_v3_adapter import make_ollama_model_step
from prompt_v3 import (
    DEFAULT_TOOL_NAMES,
    assert_prompt_axis_is_wellformed,
    build_system_prompt,
    prompt_hashes_by_condition,
)
from protocol_v3 import initialize_manifest
from scenario_review_v3 import select_approved_scenarios
from tools_v3 import TOOLS_SCHEMA, WorkspaceTools
from v3_experiment_runner import _json_array, _sensitive_fields, _tool_fields
from v3_runner import run_agent_turns
from validation_v3 import validate_run_outcome

ROOT = Path(__file__).resolve().parent
DEFAULT_REVIEW_CSV = ROOT / "data" / "scenario_review_v3.csv"
DEFAULT_PROTOCOL = ROOT / "protocols" / "v3_protocol.json"
OLLAMA_URL = "http://localhost:11434/api/chat"


def load_approved(review_csv: Path) -> list[dict]:
    with review_csv.open(encoding="utf-8", newline="") as handle:
        return select_approved_scenarios(list(csv.DictReader(handle)))


def model_digest(name: str, request_post=requests.post) -> str:
    """Pin the exact model build; the protocol requires a digest per model."""
    try:
        response = request_post("http://localhost:11434/api/show", json={"model": name}, timeout=30)
        response.raise_for_status()
        return response.json().get("digest") or f"unknown:{name}"
    except Exception:
        return f"unknown:{name}"


def completed_keys(runs_path: Path) -> set[tuple]:
    if not runs_path.exists():
        return set()
    done = set()
    with runs_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            done.add((row["model"], row["scenario"], row["condition"], row["seed"], row["retry_index"]))
    return done


def run_one(*, row, condition, model, seed, tools, model_step, tool_names, max_turns,
            forbidden_tools, retry_index=0) -> dict:
    projection = _tool_fields(_json_array(row["allowed_field_paths"], "allowed_field_paths"),
                              "allowed_field_paths")
    sensitive = _sensitive_fields(
        _json_array(row.get("forbidden_sensitive_field_paths") or "[]",
                    "forbidden_sensitive_field_paths"),
        tool_names,
    )
    run_id = f"{model.replace(':', '_')}_{row['scenario_id']}_{condition}_s{seed}_r{retry_index}"
    outcome = run_agent_turns(
        model_step=model_step, tool_executor=tools,
        initial_messages=[{"role": "user", "content": row["task"]}],
        condition=condition, projection_by_tool=projection,
        sensitive_fields_by_tool=sensitive, run_id=run_id, model=model,
        scenario=row["scenario_id"], seed=seed, max_turns=max_turns,
        system_prompt=build_system_prompt(condition=condition, tool_names=tool_names),
    )
    validation = validate_run_outcome(
        outcome["status"], outcome["final_output"], json.loads(row["success_validator"]),
        excess_sensitive_field_count=count_excess_sensitive_fields(outcome["delivery_events"]),
        forbidden_action=any(tool in forbidden_tools for tool in outcome["executed_tools"]),
    )
    return {
        "run_id": run_id, "model": model, "scenario": row["scenario_id"],
        "condition": condition, "seed": seed, "retry_index": retry_index,
        "status": outcome["status"],
        "delivery_events": outcome["delivery_events"],
        "executed_tools": outcome["executed_tools"],
        "final_output_sha256": hashlib.sha256(outcome["final_output"].encode("utf-8")).hexdigest(),
        "final_output_char_count": len(outcome["final_output"]),
        "failure_stage": outcome.get("failure_stage"),
        "failure_type": outcome.get("failure_type"),
        **validation,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="v3 controlled-disclosure study runner")
    parser.add_argument("--experiment-dir", required=True)
    parser.add_argument("--model", action="append", required=True,
                        help="ollama model tag; repeat to run several")
    parser.add_argument("--review-csv", default=str(DEFAULT_REVIEW_CSV))
    parser.add_argument("--protocol", default=str(DEFAULT_PROTOCOL))
    parser.add_argument("--conditions", default="A,B,C,D")
    parser.add_argument("--seeds", default="0")
    parser.add_argument("--max-turns", type=int, default=6)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--think", action="store_true", help="enable reasoning mode")
    parser.add_argument("--num-predict", type=int, default=1000,
                        help="max tokens per turn; bounds a rambling model")
    parser.add_argument("--limit", type=int, help="use only the first N scenarios (smoke test)")
    parser.add_argument("--git-commit", default="uncommitted")
    parser.add_argument("--dry-run", action="store_true", help="plan only, call no model")
    args = parser.parse_args(argv)

    conditions = [c.strip().upper() for c in args.conditions.split(",") if c.strip()]
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    for condition in conditions:
        if condition not in {"A", "B", "C", "D"}:
            print(f"unknown condition: {condition}")
            return 2

    assert_prompt_axis_is_wellformed(DEFAULT_TOOL_NAMES)
    rows = load_approved(Path(args.review_csv))
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        print("no approved scenarios")
        return 2

    experiment_dir = Path(args.experiment_dir)
    models = [{"name": name, "digest": model_digest(name)} for name in args.model]
    planned = [
        {"model": model["name"], "scenario": row["scenario_id"], "condition": condition,
         "seed": seed, "retry_index": 0}
        for model in models for row in rows for condition in conditions for seed in seeds
    ]
    print(f"scenarios={len(rows)} conditions={conditions} seeds={seeds} "
          f"models={[m['name'] for m in models]} -> {len(planned)} runs")

    try:
        initialize_manifest(
            experiment_dir=experiment_dir, protocol_path=args.protocol,
            scenario_path=args.review_csv, git_commit=args.git_commit,
            models=models, planned_runs=planned,
            prompt_sha256_by_condition=prompt_hashes_by_condition(DEFAULT_TOOL_NAMES),
            run_parameters={
                "temperature": args.temperature, "max_turns": args.max_turns, "seeds": seeds,
                "conditions": conditions, "think": args.think,
                "num_predict": args.num_predict,
                "tool_names": list(DEFAULT_TOOL_NAMES),
            },
        )
    except ValueError as error:
        # The freeze is doing its job: this directory already records runs made
        # under different settings.  Refuse rather than rewrite that record.
        print(f"manifest 거부: {error}")
        return 2
    if args.dry_run:
        print("dry run: manifest written, no model called")
        return 0

    runs_path = experiment_dir / "runs.jsonl"
    done = completed_keys(runs_path)
    todo = [p for p in planned
            if (p["model"], p["scenario"], p["condition"], p["seed"], p["retry_index"]) not in done]
    print(f"already done={len(done)}  todo={len(todo)}")

    tools = WorkspaceTools()
    by_id = {row["scenario_id"]: row for row in rows}
    steps = {}
    failures = 0
    for index, plan in enumerate(todo, start=1):
        key = (plan["model"], plan["seed"])
        if key not in steps:
            steps[key] = make_ollama_model_step(
                request_post=requests.post, model_name=plan["model"], tools=TOOLS_SCHEMA,
                url=OLLAMA_URL, seed=plan["seed"], temperature=args.temperature,
                think=args.think, num_predict=args.num_predict,
            )
        summary = run_one(
            row=by_id[plan["scenario"]], condition=plan["condition"], model=plan["model"],
            seed=plan["seed"], tools=tools, model_step=steps[key],
            tool_names=DEFAULT_TOOL_NAMES, max_turns=args.max_turns, forbidden_tools=frozenset(),
        )
        with runs_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(summary, ensure_ascii=False) + "\n")
        if summary["validation_status"] == "technical_failure":
            failures += 1
        flag = "" if summary["validation_status"] == "valid" else f"  [{summary['validation_status']}]"
        print(f"[{index}/{len(todo)}] {summary['run_id']}  safe={summary['safe_completion']}{flag}",
              flush=True)

    print(f"\ndone. technical failures={failures}. artifacts -> {experiment_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
