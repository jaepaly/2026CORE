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

    policies, policy_summary = build_policy_section()

    OUT.write_text(
        json.dumps({
            "scenarios": scenarios,
            "experiments": experiments,
            "summary": summary,
            "primary": {"comparison": "A vs C", "endpoint": "safe_completion", "mcnemar_p": 0.070},
            "policies": policies,
            "policy_summary": policy_summary,
        }, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"scenarios={len(scenarios)} experiments={len(experiments)} runs={len(all_rows)} -> {OUT}")
    for cond, s in summary.items():
        print(f"  {cond}: 전달 {s['delivered_sensitive_per_run']} task {s['task_success_rate']} safe {s['safe_completion_rate']}")
    print(f"  정책 작성: 시나리오 {len(policies)} · {policy_summary.get('calls', 0)} 콜")


def build_policy_section() -> tuple[dict, dict]:
    """연구 2(정책 작성)를 시나리오별로 미리 접어둔다.

    브라우저가 채점을 다시 하지 않도록 여기서 전부 계산한다. 두 실험이 같은
    scenario_id 를 쓰므로 데모의 시나리오 선택 하나로 양쪽이 함께 움직인다.
    """
    path = EXPERIMENTS / "policy-authoring" / "policies.jsonl"
    if not path.exists():
        return {}, {}

    rows = [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]
    by_scenario: dict[str, dict] = {}
    for row in rows:
        if row.get("parse_status") != "ok":
            continue
        entry = by_scenario.setdefault(row["scenario"], {
            "reviewer": sorted(row["reviewer_allowed_field_paths"]),
            "forbidden": sorted(row["reviewer_forbidden_sensitive_field_paths"]),
            "models": [],
        })
        entry["models"].append({
            "model": row["model"],
            "allowed": sorted(row["model_allowed_field_paths"]),
            "over": sorted(row["over_permission"]),
            "under": sorted(row["over_restriction"]),
            "sensitive_over": sorted(row["sensitive_over_permission"]),
            "unknown": sorted(row["unknown_paths"]),
            "run_id": row["run_id"],
        })
    for entry in by_scenario.values():
        entry["models"].sort(key=lambda m: m["model"])

    scored = [r for r in rows if r.get("parse_status") == "ok"]
    n = len(scored) or 1
    summary = {
        "calls": len(rows),
        "exact_match": round(sum(1 for r in scored if r["exact_match"]) / n, 3),
        "mean_reviewer_fields": round(sum(r["reviewer_field_count"] for r in scored) / n, 1),
        "mean_model_fields": round(sum(r["model_field_count"] for r in scored) / n, 1),
        "mean_over": round(sum(r["over_permission_count"] for r in scored) / n, 2),
        "mean_under": round(sum(r["over_restriction_count"] for r in scored) / n, 2),
        "any_sensitive_rate": round(sum(1 for r in scored if r["sensitive_over_permission_count"]) / n, 3),
    }
    return by_scenario, summary


if __name__ == "__main__":
    main()
