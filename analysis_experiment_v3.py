#!/usr/bin/env python3
"""Aggregate a v3 experiment into the three layers the protocol distinguishes.

    python analysis_experiment_v3.py --experiment-dir experiments/main

`docs/experiment_design_v3.md` requires that policy capacity, delivered exposure
and agent behaviour never be reported as one number.  This script keeps them
apart:

* **capacity**  — what a policy could permit (from the labels, no runs involved)
* **delivery**  — what the tool boundary actually handed the model
* **behaviour** — what the agent did and whether it finished the task

Only the pre-registered comparison (A vs C on ``safe_completion``) is reported as
primary; everything else is labelled secondary, and technical failures stay out
of endpoint denominators while being counted in their own right.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from scenario_review_v3 import DISCARDED_STATUS
from stats_v3 import PRIMARY_COMPARISON, analyze_primary_safe_completion, paired_bootstrap_mean_difference

ROOT = Path(__file__).resolve().parent
CONDITIONS = ("A", "B", "C", "D")


def load_runs(experiment_dir: Path) -> list[dict]:
    path = experiment_dir / "runs.jsonl"
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def capacity_by_condition(review_csv: Path) -> dict:
    """Layer 1: what each policy could permit, computed from labels alone.

    Conditions A/B apply no projection, so their capacity is every field of every
    required record; C/D are bounded by the reviewed allowed_field_paths.
    """
    with review_csv.open(encoding="utf-8", newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r["review_status"] != DISCARDED_STATUS]

    allowed_total = forbidden_total = 0
    for row in rows:
        allowed_total += len(json.loads(row["allowed_field_paths"] or "[]"))
        forbidden_total += len(json.loads(row["forbidden_sensitive_field_paths"] or "[]"))
    return {
        "scenarios": len(rows),
        "reviewed_allowed_field_paths": allowed_total,
        "declared_sensitive_field_paths": forbidden_total,
        "note": (
            "A/B apply no projection, so any declared-sensitive field is deliverable; "
            "C/D can deliver only the reviewed allowed set. This layer never depends on runs."
        ),
    }


def delivery_by_condition(runs: list[dict]) -> dict:
    """Layer 2: what the tool boundary actually delivered."""
    out = {}
    for condition in CONDITIONS:
        subset = [r for r in runs if r["condition"] == condition]
        if not subset:
            continue
        sensitive, delivered, removed, denials = [], [], [], 0
        for run in subset:
            events = run.get("delivery_events") or []
            sensitive.append(sum(len(e.get("delivered_sensitive_field_paths") or []) for e in events))
            delivered.append(sum(len(e.get("delivered_field_paths") or []) for e in events))
            removed.append(sum(len(e.get("removed_field_paths") or []) for e in events))
            denials += sum(1 for e in events if e.get("policy_decision") == "denied")
        out[condition] = {
            "runs": len(subset),
            "mean_delivered_sensitive_fields": _mean(sensitive),
            "mean_delivered_field_paths": _mean(delivered),
            "mean_removed_field_paths": _mean(removed),
            "runs_with_any_sensitive_delivery": sum(1 for value in sensitive if value),
            "tool_denials": denials,
        }
    return out


def behaviour_by_condition(runs: list[dict]) -> dict:
    """Layer 3: what the agent did, and how runs ended."""
    out = {}
    for condition in CONDITIONS:
        subset = [r for r in runs if r["condition"] == condition]
        if not subset:
            continue
        valid = [r for r in subset if r.get("validation_status") == "valid"]
        out[condition] = {
            "runs": len(subset),
            "technical_failures": sum(1 for r in subset if r.get("validation_status") == "technical_failure"),
            "max_turns_reached": sum(1 for r in subset if r.get("status") == "max_turns_reached"),
            "mean_tool_calls": _mean([len(r.get("executed_tools") or []) for r in subset]),
            "mean_distinct_records": _mean([
                len({rid for e in (r.get("delivery_events") or [])
                     for rid in (e.get("delivered_record_ids") or [])})
                for r in subset
            ]),
            # Endpoint rates use valid runs only; technical failures are reported above.
            "task_success_rate": _mean([1.0 if r.get("task_success") else 0.0 for r in valid]),
            "safe_completion_rate": _mean([1.0 if r.get("safe_completion") else 0.0 for r in valid]),
            "valid_runs": len(valid),
        }
    return out


def by_model(runs: list[dict]) -> dict:
    out = defaultdict(dict)
    for model in sorted({r["model"] for r in runs}):
        for condition in CONDITIONS:
            subset = [r for r in runs if r["model"] == model and r["condition"] == condition
                      and r.get("validation_status") == "valid"]
            if not subset:
                continue
            out[model][condition] = {
                "valid_runs": len(subset),
                "safe_completion_rate": _mean([1.0 if r.get("safe_completion") else 0.0 for r in subset]),
                "task_success_rate": _mean([1.0 if r.get("task_success") else 0.0 for r in subset]),
                "mean_delivered_sensitive_fields": _mean([
                    r.get("excess_sensitive_field_count", 0) for r in subset
                ]),
            }
    return dict(out)


def primary_analysis(runs: list[dict]) -> dict:
    """Pre-registered A vs C on safe_completion, plus a paired count CI."""
    events = [
        {"model": r["model"], "scenario": r["scenario"], "condition": r["condition"],
         "seed": r["seed"], "retry_index": r.get("retry_index", 0),
         "validation_status": r.get("validation_status"), "safe_completion": r.get("safe_completion")}
        for r in runs
    ]
    result = analyze_primary_safe_completion(events)

    # Paired bootstrap on delivered sensitive fields, same (model, scenario) unit.
    per_unit: dict[tuple, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for run in runs:
        if run["condition"] in PRIMARY_COMPARISON and run.get("validation_status") == "valid":
            per_unit[(run["model"], run["scenario"])][run["condition"]].append(
                run.get("excess_sensitive_field_count", 0)
            )
    pairs = [
        (sum(sides["A"]) / len(sides["A"]), sum(sides["C"]) / len(sides["C"]))
        for sides in per_unit.values()
        if sides.get("A") and sides.get("C")
    ]
    if pairs:
        result["delivered_sensitive_fields_a_minus_c"] = paired_bootstrap_mean_difference(
            pairs, iterations=2000, seed=1
        )
    return result


def analyse(experiment_dir: Path, review_csv: Path) -> dict:
    runs = load_runs(experiment_dir)
    if not runs:
        raise SystemExit(f"no runs found in {experiment_dir}/runs.jsonl")
    return {
        "experiment_dir": str(experiment_dir),
        "total_runs": len(runs),
        "models": sorted({r["model"] for r in runs}),
        "capacity": capacity_by_condition(review_csv),
        "delivery": delivery_by_condition(runs),
        "behaviour": behaviour_by_condition(runs),
        "by_model": by_model(runs),
        "primary": primary_analysis(runs),
        "layer_note": (
            "capacity / delivery / behaviour are separate layers. A blocked payload that was "
            "never fetched is a capacity result, not evidence that an attack was stopped."
        ),
    }


def print_summary(summary: dict) -> None:
    print(f"runs={summary['total_runs']}  models={', '.join(summary['models'])}\n")
    print(f"{'조건':4s} {'유효':>5s} {'기술실패':>7s} {'민감전달':>8s} {'task':>7s} {'safe':>7s}")
    print("-" * 44)
    for condition in CONDITIONS:
        delivery = summary["delivery"].get(condition)
        behaviour = summary["behaviour"].get(condition)
        if not behaviour:
            continue
        print(f"{condition:4s} {behaviour['valid_runs']:>5d} {behaviour['technical_failures']:>7d} "
              f"{delivery['mean_delivered_sensitive_fields']:>8.2f} "
              f"{behaviour['task_success_rate']:>7.2f} {behaviour['safe_completion_rate']:>7.2f}")

    primary = summary["primary"]
    print(f"\nprimary A vs C ({primary['endpoint']}, 단위={primary['paired_valid_unit_count']}):")
    print(f"  McNemar p = {primary['mcnemar_exact_two_sided_p']:.4f}  "
          f"risk diff = {primary['paired_risk_difference_a_minus_c']}")
    bootstrap = primary.get("delivered_sensitive_fields_a_minus_c")
    if bootstrap:
        low, high = bootstrap["bootstrap_95_ci"]
        print(f"  민감 전달 차이 A-C = {bootstrap['mean_difference_a_minus_c']:.2f} "
              f"(95% CI {low:.2f}~{high:.2f})")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="v3 experiment aggregation")
    parser.add_argument("--experiment-dir", required=True)
    parser.add_argument("--review-csv", default=str(ROOT / "data" / "scenario_review_v3.csv"))
    parser.add_argument("--out", help="summary JSON path (default: <experiment-dir>/analysis_v3.json)")
    args = parser.parse_args(argv)

    experiment_dir = Path(args.experiment_dir)
    summary = analyse(experiment_dir, Path(args.review_csv))
    out = Path(args.out) if args.out else experiment_dir / "analysis_v3.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print_summary(summary)
    print(f"\nsaved -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
