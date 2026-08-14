#!/usr/bin/env python3
"""Did the determinism fix change only what it was supposed to change?

    python verify_rerun_v3.py --original experiments/main-<m> --rerun experiments/rerun-<m>

The re-run exists because ``project_record`` iterated a set, so condition C/D
runs touching nested paths saw their tool response in a different key order on
every process.  Sorting the subfields fixes that -- but a fix that also moved the
delivery numbers would mean it changed more than key order, and the two batches
could no longer be compared or merged.

So this is a gate, not a report.  The delivery layer is built from sets and
counts and is therefore order-independent by construction: if it moved, the
edit reached something it should not have.  The behaviour layer *is* expected to
move on the affected runs, because those runs really were fed a different byte
sequence; that difference is the thing being corrected, and it is reported
rather than judged.

Exit code 0 means the re-run is usable.  Non-zero means stop and find out why
before running anything else on top of it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

CONDITIONS = ("A", "B", "C", "D")

#: Delivery means are averages of small integers over 43 scenarios; anything
#: beyond this is a real move, not floating-point noise.
DELIVERY_TOLERANCE = 0.005


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


def compare(original: list[dict], rerun: list[dict]) -> dict:
    report = {"delivery": {}, "behaviour": {}, "counts": {
        "original": len(original), "rerun": len(rerun)}}
    for condition in CONDITIONS:
        before, after = delivery_mean(original, condition), delivery_mean(rerun, condition)
        report["delivery"][condition] = {
            "original": round(before, 4), "rerun": round(after, 4),
            "delta": round(after - before, 4),
            "within_tolerance": abs(after - before) <= DELIVERY_TOLERANCE,
        }
        report["behaviour"][condition] = {
            key: {"original": round(outcome_rate(original, condition, key), 4),
                  "rerun": round(outcome_rate(rerun, condition, key), 4)}
            for key in ("task_success", "safe_completion")
        }
    changed = [
        r["run_id"] for r in rerun
        if r.get("final_output_sha256") != _sha_of(original, r["run_id"])
    ]
    report["output_changed_runs"] = len(changed)
    report["output_changed_examples"] = sorted(changed)[:10]
    return report


def _sha_of(rows: list[dict], run_id: str) -> str | None:
    for row in rows:
        if row["run_id"] == run_id:
            return row.get("final_output_sha256")
    return None


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
    print(f"원본 {report['counts']['original']} runs · 재실행 {report['counts']['rerun']} runs\n")
    print(f"{'조건':<5}{'전달(원본)':>12}{'전달(재실행)':>14}{'차이':>9}{'판정':>8}")
    print("-" * 50)
    failed = []
    for condition, stats in report["delivery"].items():
        verdict = "OK" if stats["within_tolerance"] else "불일치"
        if not stats["within_tolerance"]:
            failed.append(condition)
        print(f"{condition:<5}{stats['original']:>12.3f}{stats['rerun']:>14.3f}"
              f"{stats['delta']:>9.3f}{verdict:>8}")

    print(f"\n출력 해시가 달라진 run: {report['output_changed_runs']}")
    if report["output_changed_examples"]:
        for run_id in report["output_changed_examples"][:5]:
            print(f"  {run_id}")

    print("\n행동 계층 (바뀔 수 있음 — 판정 대상 아님)")
    for condition, stats in report["behaviour"].items():
        task = stats["task_success"]
        safe = stats["safe_completion"]
        print(f"  {condition}: task {task['original']:.3f} -> {task['rerun']:.3f}   "
              f"safe {safe['original']:.3f} -> {safe['rerun']:.3f}")

    if args.out:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        print(f"\nsaved -> {args.out}")

    if failed:
        print(f"\n❌ 전달 계층이 조건 {', '.join(failed)} 에서 움직였습니다. "
              f"수정이 키 순서 말고 다른 것도 바꿨다는 뜻이므로 멈추십시오.")
        return 1
    print("\n✅ 전달 계층 일치 — 재실행 산출물을 사용해도 됩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
