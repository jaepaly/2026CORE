#!/usr/bin/env python3
"""Summarise the policy-authoring experiment.

    python analysis_policy_authoring_v3.py --experiment-dir experiments/policy-authoring

The question this answers is not "how accurate is the model" but "which way does
it err, and does that direction change what a human has to do".  The two error
directions carry opposite consequences and are therefore never averaged into one
score:

* over-permission puts fields the reviewer excluded back in front of the agent,
  and the sensitive subset of it re-opens the leak the interface exists to close;
* over-restriction withholds fields the task needs, costing utility but leaking
  nothing.

The per-field breakdown exists because a uniform error rate and a concentrated
one imply different remedies.  If misjudgements cluster on ``notes`` and ``body``,
a review queue only needs to cover those fields; if they are spread evenly, it
cannot be narrowed and the human stays in the loop for everything.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from delivery_audit_v3 import record_domain

ROOT = Path(__file__).resolve().parent


def load_policies(experiment_dirs: list[Path]) -> list[dict]:
    seen, rows = set(), []
    for directory in experiment_dirs:
        path = directory / "policies.jsonl"
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                key = (row["model"], row["scenario"], row["seed"])
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
    return rows


def _mean(values) -> float:
    values = list(values)
    return statistics.fmean(values) if values else 0.0


def summarise(rows: list[dict]) -> dict:
    """Scored rows only; unparseable and failed calls are reported separately."""
    scored = [r for r in rows if r.get("parse_status") == "ok"]
    return {
        "calls": len(rows),
        "scored": len(scored),
        "unparseable": sum(1 for r in rows if r.get("parse_status") == "unparseable"),
        "technical_failures": sum(1 for r in rows if r.get("status") == "technical_failure"),
        "mean_model_fields": _mean(r["model_field_count"] for r in scored),
        "mean_reviewer_fields": _mean(r["reviewer_field_count"] for r in scored),
        "mean_over_permission": _mean(r["over_permission_count"] for r in scored),
        "mean_sensitive_over_permission": _mean(
            r["sensitive_over_permission_count"] for r in scored),
        "mean_over_restriction": _mean(r["over_restriction_count"] for r in scored),
        "any_sensitive_over_permission_rate": _mean(
            r["sensitive_over_permission_count"] > 0 for r in scored),
        "exact_match_rate": _mean(r["exact_match"] for r in scored),
        "mean_jaccard": _mean(r["jaccard"] for r in scored),
        "mean_precision": _mean(r["precision"] for r in scored),
        "mean_recall": _mean(r["recall"] for r in scored),
        "mean_unknown_paths": _mean(r["unknown_path_count"] for r in scored),
        "invented_path_rate": _mean(r["unknown_path_count"] > 0 for r in scored),
    }


def by_model(rows: list[dict]) -> dict:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["model"]].append(row)
    return {model: summarise(group) for model, group in sorted(grouped.items())}


def field_error_profile(rows: list[dict]) -> dict:
    """Which fields the models get wrong, and in which direction.

    Keyed by ``<record domain>.<field>`` so the same underlying field is one
    entry however it was reached -- the same rule the delivery audit uses.
    """
    over_permission: Counter = Counter()
    over_restriction: Counter = Counter()
    opportunities: Counter = Counter()
    for row in rows:
        if row.get("parse_status") != "ok":
            continue
        for path in row["over_permission"]:
            tool, _, field = path.partition(".")
            over_permission[f"{record_domain(tool)}.{field}"] += 1
        for path in row["over_restriction"]:
            tool, _, field = path.partition(".")
            over_restriction[f"{record_domain(tool)}.{field}"] += 1
        for path in row["reviewer_allowed_field_paths"]:
            tool, _, field = path.partition(".")
            opportunities[f"{record_domain(tool)}.{field}"] += 1
    return {
        "over_permission": dict(over_permission.most_common()),
        "over_restriction": dict(over_restriction.most_common()),
        "reviewer_allowed_occurrences": dict(opportunities.most_common()),
    }


def sensitive_field_profile(rows: list[dict]) -> dict:
    """How often each forbidden field was granted, out of the times it was forbidden."""
    granted: Counter = Counter()
    forbidden: Counter = Counter()
    for row in rows:
        if row.get("parse_status") != "ok":
            continue
        for path in row["reviewer_forbidden_sensitive_field_paths"]:
            tool, _, field = path.partition(".")
            forbidden[f"{record_domain(tool)}.{field}"] += 1
        for path in row["sensitive_over_permission"]:
            tool, _, field = path.partition(".")
            granted[f"{record_domain(tool)}.{field}"] += 1
    return {
        key: {
            "forbidden_in_scenarios": forbidden[key],
            "granted_by_model": granted.get(key, 0),
            "grant_rate": granted.get(key, 0) / forbidden[key] if forbidden[key] else 0.0,
        }
        for key in sorted(forbidden, key=lambda k: -granted.get(k, 0))
    }


def scenario_agreement(rows: list[dict]) -> dict:
    """Scenarios where every model over-permits are a label-difficulty signal.

    If all four independently allow a field the reviewer excluded, the more
    likely reading is that the task text underdetermines the boundary -- worth
    reporting rather than scoring silently as four separate model errors.
    """
    grouped = defaultdict(list)
    for row in rows:
        if row.get("parse_status") == "ok":
            grouped[row["scenario"]].append(row)
    unanimous_over, unanimous_exact = [], []
    for scenario, group in sorted(grouped.items()):
        if len(group) < 2:
            continue
        if all(r["over_permission_count"] > 0 for r in group):
            unanimous_over.append(scenario)
        if all(r["exact_match"] for r in group):
            unanimous_exact.append(scenario)
    return {
        "scenarios": len(grouped),
        "all_models_over_permit": unanimous_over,
        "all_models_exact_match": unanimous_exact,
    }


def analyse(experiment_dirs: list[Path]) -> dict:
    rows = load_policies(experiment_dirs)
    return {
        "total_calls": len(rows),
        "models": sorted({r["model"] for r in rows}),
        "overall": summarise(rows),
        "by_model": by_model(rows),
        "field_errors": field_error_profile(rows),
        "sensitive_fields": sensitive_field_profile(rows),
        "agreement": scenario_agreement(rows),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="policy-authoring analysis")
    parser.add_argument("--experiment-dir", action="append", required=True)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    directories = [Path(d) for d in args.experiment_dir]
    summary = analyse(directories)
    if not summary["total_calls"]:
        print("no policies found")
        return 2

    print(f"calls={summary['total_calls']}  models={', '.join(summary['models'])}")
    overall = summary["overall"]
    print(f"파싱 실패 {overall['unparseable']}  기술 실패 {overall['technical_failures']}\n")

    header = (f"{'model':<15}{'allow':>7}{'human':>7}{'over':>7}{'over-sens':>11}"
              f"{'under':>7}{'exact':>7}{'recall':>8}")
    print(header)
    print("-" * len(header))

    def line(label: str, stats: dict) -> str:
        return (f"{label:<15}{stats['mean_model_fields']:7.1f}{stats['mean_reviewer_fields']:7.1f}"
                f"{stats['mean_over_permission']:7.2f}"
                f"{stats['mean_sensitive_over_permission']:11.2f}"
                f"{stats['mean_over_restriction']:7.2f}{stats['exact_match_rate']:7.2f}"
                f"{stats['mean_recall']:8.2f}")

    for model, stats in summary["by_model"].items():
        print(line(model, stats))
    print("-" * len(header))
    print(line("ALL", overall))
    print("  over=과잉 허용  over-sens=그중 민감 필드  under=과잉 차단  (시나리오당 필드 수)")

    print(f"\n민감 필드를 한 번이라도 허용한 비율: {overall['any_sensitive_over_permission_rate']:.1%}")
    print(f"어휘에 없는 필드를 지어낸 비율: {overall['invented_path_rate']:.1%}")

    sensitive = summary["sensitive_fields"]
    if sensitive:
        print("\n금지 민감 필드별 허용률")
        for key, stats in sensitive.items():
            print(f"  {key:34} {stats['granted_by_model']:3}/{stats['forbidden_in_scenarios']:3}"
                  f"  ({stats['grant_rate']:.1%})")

    out = Path(args.out) if args.out else directories[0] / "analysis_policy_authoring.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
