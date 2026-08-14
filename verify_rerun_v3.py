#!/usr/bin/env python3
"""Did the determinism fix change only what it was supposed to change?

    python verify_rerun_v3.py --original experiments/main-<m> --rerun experiments/rerun-<m>

The re-run exists because ``project_record`` iterated a set, so condition C/D
runs touching nested paths saw their tool response in a different key order on
every process.  Sorting the subfields fixes that -- but a fix that also moved
*what* the tools returned would mean it changed more than key order, and the two
batches could no longer be compared or merged.

Why this gate does not compare aggregate delivery means
-------------------------------------------------------
An earlier version failed the re-run because condition A's mean delivery moved
0.500 -> 0.442.  That verdict was wrong, and the reason matters.  Aggregate
delivery moves for two quite different causes:

1. the fix reached something it should not have -- the thing we must catch; or
2. the model called *different tools*, so different records were fetched.

Local inference is not reproducible even at temperature 0: in the 8/14 re-run,
266 of 688 runs took a different tool path, and conditions A/B cannot be touched
by the fix at all (``allowed_field_paths is None`` returns the record untouched
before any sorting happens).  A tolerance on the mean therefore cannot separate
cause 1 from cause 2, and with a 0.005 band it reports cause 2 as failure.

So the gate tests the invariant directly instead.  Restricted to runs where the
model took **the same tool path** -- same tools, same argument hashes -- the
fields each call delivered and removed must be identical as *sets*.  Sets ignore
key order, which is precisely what the fix changed, so any difference here is
the fix reaching further than intended.  On the 8/14 re-run this held for all
422 same-path runs.

Delivery means are still reported, as description rather than verdict, together
with how far the two batches diverged behaviourally.

Exit code 0 means the re-run is usable.  Non-zero means stop and find out why
before running anything else on top of it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

CONDITIONS = ("A", "B", "C", "D")

#: Conditions whose projection removes every sensitive field by construction.
#: Their delivery is 0 by definition, so any drift is a broken contract, not noise.
PROJECTED_CONDITIONS = ("C", "D")

#: A same-path comparison over too few runs proves nothing.  If inference drifted
#: so far that almost nothing is comparable, say so rather than pass silently.
MIN_COMPARABLE_FRACTION = 0.10


def load(directory: Path) -> list[dict]:
    path = directory / "runs.jsonl"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def delivery_mean(rows: list[dict], condition: str) -> float:
    group = [r for r in rows if r["condition"] == condition]
    if not group:
        return 0.0
    return sum(r.get("excess_sensitive_field_count", 0) for r in group) / len(group)


def outcome_rate(rows: list[dict], condition: str, key: str) -> float:
    group = [r for r in rows if r["condition"] == condition]
    if not group:
        return 0.0
    return sum(1 for r in group if r.get(key)) / len(group)


def tool_path(run: dict) -> tuple:
    """The model's tool path: which tools, with which arguments, in which order."""
    return tuple((event.get("tool_name"), event.get("requested_args_sha256"))
                 for event in run.get("delivery_events", []))


def delivered_sets(run: dict) -> tuple:
    """What each call delivered, as sets -- order-independent by construction."""
    return tuple((frozenset(event.get("delivered_field_paths") or []),
                  frozenset(event.get("removed_field_paths") or []),
                  frozenset(event.get("delivered_record_ids") or []))
                 for event in run.get("delivery_events", []))


def compare(original: list[dict], rerun: list[dict]) -> dict:
    before_by_id = {row["run_id"]: row for row in original}
    after_by_id = {row["run_id"]: row for row in rerun}
    shared = sorted(set(before_by_id) & set(after_by_id))

    same_path, diverged, violations = [], [], []
    for run_id in shared:
        before, after = before_by_id[run_id], after_by_id[run_id]
        if tool_path(before) != tool_path(after):
            diverged.append(run_id)
            continue
        same_path.append(run_id)
        if delivered_sets(before) != delivered_sets(after):
            violations.append(run_id)

    report = {
        "counts": {"original": len(original), "rerun": len(rerun), "shared": len(shared)},
        "order_invariance": {
            "same_tool_path_runs": len(same_path),
            "field_set_violations": len(violations),
            "violation_examples": violations[:10],
            "passed": not violations,
        },
        "behavioural_divergence": {
            "diverged_tool_path_runs": len(diverged),
            "diverged_fraction": round(len(diverged) / len(shared), 4) if shared else 0.0,
            "output_hash_changed": sum(
                1 for run_id in shared
                if before_by_id[run_id].get("final_output_sha256")
                != after_by_id[run_id].get("final_output_sha256")),
        },
        "projection_contract": {},
        "delivery": {},
        "behaviour": {},
    }

    for condition in CONDITIONS:
        before_mean, after_mean = delivery_mean(original, condition), delivery_mean(rerun, condition)
        report["delivery"][condition] = {
            "original": round(before_mean, 4), "rerun": round(after_mean, 4),
            "delta": round(after_mean - before_mean, 4),
        }
        report["behaviour"][condition] = {
            key: {"original": round(outcome_rate(original, condition, key), 4),
                  "rerun": round(outcome_rate(rerun, condition, key), 4)}
            for key in ("task_success", "safe_completion")
        }

    for condition in PROJECTED_CONDITIONS:
        held = (report["delivery"][condition]["original"] == 0.0
                and report["delivery"][condition]["rerun"] == 0.0)
        report["projection_contract"][condition] = {
            "original": report["delivery"][condition]["original"],
            "rerun": report["delivery"][condition]["rerun"],
            "held": held,
        }

    comparable = len(same_path) / len(shared) if shared else 0.0
    report["order_invariance"]["comparable_fraction"] = round(comparable, 4)
    report["order_invariance"]["enough_to_judge"] = comparable >= MIN_COMPARABLE_FRACTION
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="re-run verification gate")
    parser.add_argument("--original", action="append", required=True)
    parser.add_argument("--rerun", action="append", required=True)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    original = [row for d in args.original for row in load(Path(d))]
    rerun = [row for d in args.rerun for row in load(Path(d))]
    if not original or not rerun:
        print("원본 또는 재실행 산출물이 비어 있습니다")
        return 2

    report = compare(original, rerun)
    counts = report["counts"]
    print(f"원본 {counts['original']} runs · 재실행 {counts['rerun']} runs · 공통 {counts['shared']}\n")

    invariance = report["order_invariance"]
    print("[게이트 1] 순서 불변성 — 같은 도구 경로에서 전달 필드 집합이 같은가")
    print(f"  같은 도구 경로 run : {invariance['same_tool_path_runs']} "
          f"({invariance['comparable_fraction']:.0%})")
    print(f"  필드 집합 불일치   : {invariance['field_set_violations']}")
    for run_id in invariance["violation_examples"][:5]:
        print(f"    {run_id}")

    print("\n[게이트 2] projection 계약 — C/D 전달은 정의상 0")
    for condition, stats in report["projection_contract"].items():
        mark = "OK" if stats["held"] else "위반"
        print(f"  {condition}: {stats['original']:.3f} -> {stats['rerun']:.3f}  {mark}")

    divergence = report["behavioural_divergence"]
    print(f"\n[참고] 모델 비결정성 — 판정 대상 아님")
    print(f"  도구 경로가 달라진 run : {divergence['diverged_tool_path_runs']} "
          f"({divergence['diverged_fraction']:.0%})")
    print(f"  출력 해시가 달라진 run : {divergence['output_hash_changed']}")

    print("\n[참고] 조건별 전달 평균 (비결정성 때문에 움직일 수 있음)")
    for condition, stats in report["delivery"].items():
        print(f"  {condition}: {stats['original']:.3f} -> {stats['rerun']:.3f} "
              f"({stats['delta']:+.3f})")

    print("\n[참고] 행동 계층")
    for condition, stats in report["behaviour"].items():
        task, safe = stats["task_success"], stats["safe_completion"]
        print(f"  {condition}: task {task['original']:.3f} -> {task['rerun']:.3f}   "
              f"safe {safe['original']:.3f} -> {safe['rerun']:.3f}")

    if args.out:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        print(f"\nsaved -> {args.out}")

    failures = []
    if not invariance["passed"]:
        failures.append(
            f"순서 불변성 위반 {invariance['field_set_violations']}건 — "
            f"같은 도구 경로인데 전달 필드가 달라졌습니다. 수정이 키 순서 말고 다른 것도 바꿨다는 뜻입니다")
    if not invariance["enough_to_judge"]:
        failures.append(
            f"비교 가능한 run 이 {invariance['comparable_fraction']:.0%} 뿐이라 판정할 수 없습니다")
    broken = [c for c, s in report["projection_contract"].items() if not s["held"]]
    if broken:
        failures.append(f"projection 계약 위반: 조건 {', '.join(broken)} 의 전달이 0이 아닙니다")

    if failures:
        print("\n❌ 중단하십시오.")
        for line in failures:
            print(f"  - {line}")
        return 1
    print("\n✅ 수정은 키 순서만 바꿨습니다 — 재실행 산출물을 사용해도 됩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
