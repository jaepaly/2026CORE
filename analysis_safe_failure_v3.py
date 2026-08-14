#!/usr/bin/env python3
"""How runs ended, and whether the answer stayed as clean as the interface.

    python analysis_safe_failure_v3.py --experiment-dir experiments/rerun-qwen2.5-3b [...]

Two things the main analysis cannot say, both read off the classification the
runner now records:

**Did projection hold at the output?**  ``A 0.50 -> C 0.00`` is a statement about
what the tool boundary delivered.  If a condition-C run states a phone number the
run never delivered, the interface worked and the claim a reader cares about
still failed.  ``leaked_undelivered_value`` counts exactly that case, and the
expected result is zero -- which is worth publishing as a check that passed
rather than leaving unmeasured.

**How did the 95% fail?**  Task success sits at a few percent, so nearly every
run is a failure, and until now all of them looked alike in the artifacts.  A run
that says "확인할 수 없습니다" hands the user a signal to act on; a run that
quietly reports a wrong date does not.  Whether an interface that withholds
fields pushes models toward the first or the second is the utility-side question
the endpoint had no power to answer.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

CONDITIONS = ("A", "B", "C", "D")
CLASSES = ("answered", "acknowledged_limitation", "silent_incomplete",
           "leaked_undelivered_value")

ROOT = Path(__file__).resolve().parent


def load_runs(directories) -> list[dict]:
    seen, rows = set(), []
    for directory in directories:
        path = Path(directory) / "runs.jsonl"
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                key = (row["model"], row["scenario"], row["condition"],
                       row["seed"], row.get("retry_index", 0))
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
    return rows


def _rate(rows, predicate) -> float:
    rows = list(rows)
    return sum(1 for r in rows if predicate(r)) / len(rows) if rows else 0.0


def by_condition(rows: list[dict]) -> dict:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["condition"]].append(row)
    summary = {}
    for condition in CONDITIONS:
        group = grouped.get(condition, [])
        if not group:
            continue
        classes = Counter(r.get("outcome_class") for r in group)
        failures = [r for r in group if r.get("outcome_class") != "answered"]
        summary[condition] = {
            "runs": len(group),
            "classes": {name: classes.get(name, 0) for name in CLASSES},
            "leaked_runs": classes.get("leaked_undelivered_value", 0),
            # Among runs that did not finish the task, how many told the user so.
            # This is the safe-failure rate proper: the denominator is failures,
            # not all runs, so a condition is not rewarded for succeeding more.
            "safe_failure_rate_of_failures": _rate(
                failures, lambda r: r.get("outcome_class") == "acknowledged_limitation"),
            "silent_rate_of_failures": _rate(
                failures, lambda r: r.get("outcome_class") == "silent_incomplete"),
            "failures": len(failures),
        }
    return summary


def by_model(rows: list[dict]) -> dict:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["model"]].append(row)
    return {model: by_condition(group) for model, group in sorted(grouped.items())}


def leaked_detail(rows: list[dict]) -> dict:
    paths: Counter = Counter()
    per_condition: Counter = Counter()
    runs = []
    for row in rows:
        leaked = row.get("leaked_value_paths") or []
        if not leaked:
            continue
        per_condition[row["condition"]] += 1
        paths.update(leaked)
        runs.append({"run_id": row["run_id"], "condition": row["condition"],
                     "paths": leaked})
    return {"by_condition": dict(per_condition), "by_path": dict(paths.most_common()),
            "runs": runs[:40]}


def analyse(directories) -> dict:
    rows = load_runs(directories)
    classified = [r for r in rows if r.get("outcome_class")]
    return {
        "total_runs": len(rows),
        "classified_runs": len(classified),
        "models": sorted({r["model"] for r in classified}),
        "by_condition": by_condition(classified),
        "by_model": by_model(classified),
        "leaked": leaked_detail(classified),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="safe-failure analysis")
    parser.add_argument("--experiment-dir", action="append", required=True)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    summary = analyse(args.experiment_dir)
    if not summary["classified_runs"]:
        print("분류된 run 이 없습니다 — safe_failure 분류가 붙은 뒤 실행된 산출물이 필요합니다")
        return 2

    print(f"runs={summary['classified_runs']}  models={', '.join(summary['models'])}\n")
    header = (f"{'조건':<5}{'run':>6}{'완수':>7}{'한계인정':>9}{'무신호':>8}"
              f"{'값누출':>8}{'실패중 안전실패':>16}")
    print(header)
    print("-" * 62)
    for condition, stats in summary["by_condition"].items():
        classes = stats["classes"]
        print(f"{condition:<5}{stats['runs']:>6}{classes['answered']:>7}"
              f"{classes['acknowledged_limitation']:>9}{classes['silent_incomplete']:>8}"
              f"{classes['leaked_undelivered_value']:>8}"
              f"{stats['safe_failure_rate_of_failures']:>16.2f}")

    leaked = summary["leaked"]
    total_leaked = sum(leaked["by_condition"].values())
    print(f"\n전달되지 않은 민감 값이 출력에 나타난 run: {total_leaked}")
    if total_leaked:
        print("  조건별:", leaked["by_condition"])
        for path, count in list(leaked["by_path"].items())[:10]:
            print(f"    {path}: {count}")
        print("  ⚠ projection 은 전달을 막았지만 답변까지 막지는 못했습니다.")
    else:
        print("  0건 — 전달 차단이 답변 수준에서도 유지되었습니다.")

    out = Path(args.out) if args.out else Path(args.experiment_dir[0]) / "safe_failure.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
