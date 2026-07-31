#!/usr/bin/env python3
"""데모 replay 인덱스 생성.

scenario_review_v3.csv 의 승인 행에서 {id, name, task} 를 추출하고,
experiments/ 아래 본 실험 디렉터리 목록을 붙여 demo/replay_index.json 을 만든다.
브라우저에서 CSV 를 직접 파싱하지 않기 위한 빌드 단계다.

    python demo/build_replay_index.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEW_CSV = ROOT / "data" / "scenario_review_v3.csv"
EXPERIMENTS = ROOT / "experiments"
OUT = Path(__file__).resolve().parent / "replay_index.json"


def main() -> None:
    scenarios = []
    with REVIEW_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("review_status") or "").strip() != "approved":
                continue
            scenarios.append({
                "id": row["scenario_id"],
                "name": row["name"],
                "task": row["task"],
            })

    experiments = []
    all_rows = []
    for d in sorted(EXPERIMENTS.glob("main-*")):
        runs = d / "runs.jsonl"
        if not runs.exists():
            continue
        model = None
        manifest = d / "manifest.json"
        if manifest.exists():
            models = json.loads(manifest.read_text(encoding="utf-8")).get("models") or []
            if models:
                first = models[0]
                model = first.get("name") or first.get("model") if isinstance(first, dict) else first
        rows = [json.loads(line) for line in runs.open(encoding="utf-8") if line.strip()]
        all_rows.extend(rows)
        experiments.append({
            "dir": f"experiments/{d.name}",
            "model": model or d.name.removeprefix("main-"),
            "runs": len(rows),
        })

    # v3 조건별 요약 — 데모 메트릭의 단일 출처 (원천: runs.jsonl)
    summary = {}
    for cond in ["A", "B", "C", "D"]:
        rows = [r for r in all_rows if r.get("condition") == cond]
        n = len(rows)
        summary[cond] = {
            "n": n,
            "delivered_sensitive_per_run": round(
                sum(r.get("excess_sensitive_field_count", 0) for r in rows) / n, 2) if n else 0,
            "task_success_rate": round(sum(1 for r in rows if r.get("task_success")) / n, 3) if n else 0,
            "safe_completion_rate": round(sum(1 for r in rows if r.get("safe_completion")) / n, 3) if n else 0,
        }

    OUT.write_text(
        json.dumps({
            "scenarios": scenarios,
            "experiments": experiments,
            "summary": summary,
            "primary": {"comparison": "A vs C", "endpoint": "safe_completion", "mcnemar_p": 0.070},
        }, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"scenarios={len(scenarios)} experiments={len(experiments)} runs={len(all_rows)} -> {OUT}")
    for cond, s in summary.items():
        print(f"  {cond}: 전달 {s['delivered_sensitive_per_run']} task {s['task_success_rate']} safe {s['safe_completion_rate']}")


if __name__ == "__main__":
    main()
