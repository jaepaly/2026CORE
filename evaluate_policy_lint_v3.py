#!/usr/bin/env python3
"""Does the static policy check earn its place in the pipeline?

    python evaluate_policy_lint_v3.py

The results section proposes "model drafts -> schema check -> human approves the
rest".  That is only worth proposing if the check actually separates broken
policies from workable ones *without* seeing the reviewer labels.  Two things
have to hold, and this script measures both:

1. **It must not fire on the human policies.**  The reviewed labels are the
   standard the pipeline is trying to approach; a check that rejects them is
   measuring its own convention, not executability.
2. **Policies it passes must be closer to that standard** than the ones it
   rejects -- otherwise it is flagging noise.

Neither measurement feeds back into the check: ``policy_lint_v3`` never reads a
label.  The reviewer labels are used here only to score it after the fact.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter
from pathlib import Path

from policy_lint_v3 import has_errors, lint_policy, workspace_tool_graph

ROOT = Path(__file__).resolve().parent


def load_reviewer_policies(review_csv: Path) -> list[dict]:
    with review_csv.open(encoding="utf-8", newline="") as handle:
        return [
            {"scenario": row["scenario_id"],
             "paths": json.loads(row["allowed_field_paths"])}
            for row in csv.DictReader(handle)
            if (row.get("review_status") or "").strip() == "approved"
        ]


def load_model_policies(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return [r for r in rows if r.get("parse_status") == "ok"]


def _mean(values) -> float:
    values = list(values)
    return statistics.fmean(values) if values else 0.0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="policy lint evaluation")
    parser.add_argument("--policies", default=str(ROOT / "experiments" / "policy-authoring" / "policies.jsonl"))
    parser.add_argument("--review-csv", default=str(ROOT / "data" / "scenario_review_v3.csv"))
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    graph = workspace_tool_graph()

    reviewer = load_reviewer_policies(Path(args.review_csv))
    reviewer_flagged = [r for r in reviewer if lint_policy(r["paths"], graph)]
    reviewer_errors = [r for r in reviewer if has_errors(lint_policy(r["paths"], graph))]

    model = load_model_policies(Path(args.policies))
    codes: Counter = Counter()
    errored, clean = [], []
    for row in model:
        found = lint_policy(row["model_allowed_field_paths"], graph)
        for diagnostic in found:
            codes[diagnostic.code] += 1
        (errored if has_errors(found) else clean).append(row)

    summary = {
        "reviewer_policies": len(reviewer),
        "reviewer_flagged_any": len(reviewer_flagged),
        "reviewer_flagged_error": len(reviewer_errors),
        "model_policies": len(model),
        "model_rejected": len(errored),
        "model_passed": len(clean),
        "diagnostic_counts": dict(codes.most_common()),
        "passed_mean_recall": _mean(r["recall"] for r in clean),
        "rejected_mean_recall": _mean(r["recall"] for r in errored),
        "passed_mean_jaccard": _mean(r["jaccard"] for r in clean),
        "rejected_mean_jaccard": _mean(r["jaccard"] for r in errored),
        "passed_sensitive_rate": _mean(r["sensitive_over_permission_count"] > 0 for r in clean),
        "rejected_sensitive_rate": _mean(r["sensitive_over_permission_count"] > 0 for r in errored),
    }

    print(f"[검증 1] 인간 라벨 {summary['reviewer_policies']}개 중 "
          f"error 판정 {summary['reviewer_flagged_error']}개 · "
          f"warning 포함 {summary['reviewer_flagged_any']}개")
    if summary["reviewer_flagged_error"]:
        print("  ⚠ 검증기가 기준 자체를 거부합니다 — 규칙이 관행을 측정하고 있을 수 있습니다")
        for row in reviewer_errors[:5]:
            print(f"    {row['scenario']}: {[str(d) for d in lint_policy(row['paths'], graph)]}")
    else:
        print("  기준을 하나도 거부하지 않습니다 — 규칙이 실행 가능성만 본다는 뜻입니다")

    print(f"\n[검증 2] 모델 정책 {summary['model_policies']}개 중 "
          f"거부 {summary['model_rejected']} ({summary['model_rejected']/max(1,summary['model_policies']):.0%}) · "
          f"통과 {summary['model_passed']}")
    for code, count in summary["diagnostic_counts"].items():
        print(f"  {code}: {count}")

    print(f"\n{'':22}{'통과':>10}{'거부':>10}")
    print("-" * 42)
    for label, a, b in (
        ("평균 재현율", summary["passed_mean_recall"], summary["rejected_mean_recall"]),
        ("평균 Jaccard", summary["passed_mean_jaccard"], summary["rejected_mean_jaccard"]),
        ("민감 필드 허용률", summary["passed_sensitive_rate"], summary["rejected_sensitive_rate"]),
    ):
        print(f"{label:20}{a:10.3f}{b:10.3f}")

    print(f"\n검증기는 라벨을 읽지 않고 {summary['model_rejected']}개를 걸러냅니다. "
          f"사람이 볼 후보가 {summary['model_policies']} -> {summary['model_passed']}개로 줄어듭니다.")

    out = Path(args.out) if args.out else ROOT / "experiments" / "policy-authoring" / "lint_evaluation.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
