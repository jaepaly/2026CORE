#!/usr/bin/env python3
"""Ask each model to author the least-privilege policy, then score it.

    python run_policy_authoring_v3.py --experiment-dir experiments/policy-authoring \
        --model qwen2.5:3b --model qwen2.5:7b --model llama3.1:8b --model qwen3:8b

One call per (model, scenario, seed) -- 43 scenarios x 4 models is 172 calls, an
evening on one machine.  Results append to ``policies.jsonl`` immediately and a
rerun skips what is already there, matching the main runner so a crash costs one
call rather than the batch.

This runner never touches the main study.  It reads the same frozen labels and
the same synthetic fixtures, and writes to its own directory.

Artifacts stay value-free by the same rule as the main study: field paths, counts
and a sha256 of the reply, never the reply text.  Field paths are the unit of
analysis here, and they are schema names rather than record contents.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import requests

from ollama_v3_adapter import make_ollama_model_step
from policy_authoring_v3 import (
    build_field_vocabulary,
    build_policy_prompt,
    flatten_vocabulary,
    parse_policy_response,
    score_policy,
)
from run_experiment_v3 import load_approved, model_digest
from tools_v3 import WorkspaceTools

ROOT = Path(__file__).resolve().parent
DEFAULT_REVIEW_CSV = ROOT / "data" / "scenario_review_v3.csv"
OLLAMA_URL = "http://localhost:11434/api/chat"


def completed_keys(path: Path) -> set[tuple]:
    if not path.exists():
        return set()
    done = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            done.add((row["model"], row["scenario"], row["seed"]))
    return done


def author_one(*, row, model, seed, vocabulary, model_step) -> dict:
    """One authoring call plus its score against the reviewed labels."""
    messages = build_policy_prompt(row["task"], vocabulary)
    run_id = f"{model.replace(':', '_')}_{row['scenario_id']}_policy_s{seed}"
    try:
        reply = model_step(messages)
        text = reply.get("content", "") or ""
        status = "completed"
    except Exception as error:  # network, timeout, model missing
        text, status = "", "technical_failure"
        failure = f"{type(error).__name__}: {error}"

    parsed = parse_policy_response(text, vocabulary) if status == "completed" else {
        "parse_status": "technical_failure", "allowed_field_paths": [], "unknown_paths": []
    }
    reviewer_allowed = json.loads(row["allowed_field_paths"])
    reviewer_forbidden = json.loads(row.get("forbidden_sensitive_field_paths") or "[]")
    scored = score_policy(
        model_paths=parsed["allowed_field_paths"],
        reviewer_allowed=reviewer_allowed,
        reviewer_forbidden_sensitive=reviewer_forbidden,
    )
    record = {
        "run_id": run_id, "model": model, "scenario": row["scenario_id"], "seed": seed,
        "status": status,
        "parse_status": parsed["parse_status"],
        "model_allowed_field_paths": parsed["allowed_field_paths"],
        "unknown_paths": parsed["unknown_paths"],
        "unknown_path_count": len(parsed["unknown_paths"]),
        "reviewer_allowed_field_paths": sorted(reviewer_allowed),
        "reviewer_forbidden_sensitive_field_paths": sorted(reviewer_forbidden),
        "vocabulary_size": len(flatten_vocabulary(vocabulary)),
        "response_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "response_char_count": len(text),
        **scored,
    }
    if status == "technical_failure":
        record["failure_type"] = failure
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="policy-authoring experiment")
    parser.add_argument("--experiment-dir", required=True)
    parser.add_argument("--model", action="append", required=True)
    parser.add_argument("--review-csv", default=str(DEFAULT_REVIEW_CSV))
    parser.add_argument("--seeds", default="0")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--num-predict", type=int, default=1000)
    parser.add_argument("--think", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--git-commit", default="uncommitted")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    rows = load_approved(Path(args.review_csv))
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        print("no approved scenarios")
        return 2

    tools = WorkspaceTools()
    vocabulary = build_field_vocabulary(tools)
    experiment_dir = Path(args.experiment_dir)
    experiment_dir.mkdir(parents=True, exist_ok=True)

    planned = [
        {"model": name, "scenario": row["scenario_id"], "seed": seed}
        for name in args.model for row in rows for seed in seeds
    ]
    print(f"scenarios={len(rows)} models={args.model} seeds={seeds} -> {len(planned)} calls")
    print(f"vocabulary={len(flatten_vocabulary(vocabulary))} paths over {len(vocabulary)} tools")

    manifest = {
        "experiment": "policy_authoring_v3",
        "scenario_csv_sha256": hashlib.sha256(
            Path(args.review_csv).read_bytes()).hexdigest(),
        "prompt_sha256": hashlib.sha256(
            json.dumps(build_policy_prompt("<task>", vocabulary),
                       ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
        "vocabulary": {tool: sorted(fields) for tool, fields in vocabulary.items()},
        "models": [{"name": name, "digest": model_digest(name)} for name in args.model],
        "run_parameters": {
            "temperature": args.temperature, "seeds": seeds,
            "num_predict": args.num_predict, "think": args.think,
        },
        "git_commit": args.git_commit,
        "planned_calls": len(planned),
    }
    manifest_path = experiment_dir / "manifest.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        drift = [
            key for key in ("scenario_csv_sha256", "prompt_sha256", "run_parameters", "vocabulary")
            if existing.get(key) != manifest[key]
        ]
        if drift:
            # Same refusal the main runner makes: this directory already records
            # calls made under other settings, so appending would mix them.
            print(f"manifest 거부: {', '.join(drift)} 가 기존 기록과 다릅니다")
            return 2
    else:
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.dry_run:
        print("dry run: manifest written, no model called")
        return 0

    policies_path = experiment_dir / "policies.jsonl"
    done = completed_keys(policies_path)
    todo = [p for p in planned if (p["model"], p["scenario"], p["seed"]) not in done]
    print(f"already done={len(done)}  todo={len(todo)}")

    by_id = {row["scenario_id"]: row for row in rows}
    steps: dict[tuple, object] = {}
    failures = 0
    for index, plan in enumerate(todo, start=1):
        key = (plan["model"], plan["seed"])
        if key not in steps:
            steps[key] = make_ollama_model_step(
                request_post=requests.post, model_name=plan["model"], tools=[],
                url=OLLAMA_URL, seed=plan["seed"], temperature=args.temperature,
                think=args.think, num_predict=args.num_predict,
            )
        record = author_one(row=by_id[plan["scenario"]], model=plan["model"], seed=plan["seed"],
                            vocabulary=vocabulary, model_step=steps[key])
        with policies_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        if record["status"] == "technical_failure":
            failures += 1
        note = "" if record["parse_status"] == "ok" else f"  [{record['parse_status']}]"
        print(f"[{index}/{len(todo)}] {record['run_id']}  "
              f"허용 {record['model_field_count']} (기준 {record['reviewer_field_count']})  "
              f"과잉 {record['over_permission_count']} "
              f"(민감 {record['sensitive_over_permission_count']})  "
              f"차단 {record['over_restriction_count']}{note}", flush=True)

    print(f"\ndone. technical failures={failures}. artifacts -> {experiment_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
