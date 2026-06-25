#!/usr/bin/env python3
"""Analyze v2 agent-loop experiment results.

The committed v2 result file stores full run records in
`output/multi_model_results_v2.json`.  Earlier plotting code expected a
summary-only field named `accessed_ids_count`, which made the access line in
the README figures appear as zero.  This script normalizes both shapes:

- full records with `accessed_ids: [...]`
- compact records with `accessed_ids_count: n`

For headline figures we deduplicate by
`(model, scenario, condition, seed)` and keep the last occurrence, because the
current result file contains repeated runs for some combinations.
"""

from __future__ import annotations

import json
import math
import os
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
FIG_DIR = ROOT / "docs" / "figures"

RUNS_JSONL = OUTPUT_DIR / "runs.jsonl"
RESULTS_JSON = OUTPUT_DIR / "multi_model_results_v2.json"
SUMMARY_JSON = OUTPUT_DIR / "analysis_summary_v2.json"
AUDIT_JSON = OUTPUT_DIR / "analysis_audit_v2.json"

MODELS = ["qwen3:8b", "llama3.1:8b", "qwen2.5:7b"]
CONDITIONS = ["A", "B", "C"]
SEEDS = list(range(10))


def load_scenarios() -> list[dict]:
    path = DATA_DIR / "scenarios_v2.json"
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data["scenarios"]


def load_runs() -> list[dict]:
    """Load full run records.

    Prefer the committed JSON result file.  Fall back to `runs.jsonl` if someone
    is running a fresh local experiment and has not yet exported the JSON.
    """

    if RESULTS_JSON.exists():
        with RESULTS_JSON.open(encoding="utf-8") as f:
            rows = json.load(f)
        if isinstance(rows, list):
            return rows

    rows: list[dict] = []
    if RUNS_JSONL.exists():
        with RUNS_JSONL.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
    return rows


def normalize_runs(rows: list[dict], scenarios: list[dict]) -> list[dict]:
    minimum_by_scenario = {s["id"]: set(s.get("minimum", [])) for s in scenarios}
    normalized = []

    for r in rows:
        row = dict(r)
        accessed = row.get("accessed_ids")
        if isinstance(accessed, list):
            accessed_set = set(accessed)
            accessed_count = len(accessed_set)
        else:
            accessed_set = set()
            accessed_count = int(row.get("accessed_ids_count", 0) or 0)

        minimum = minimum_by_scenario.get(row.get("scenario"), set())
        required_covered = len(accessed_set & minimum)
        excess = len(accessed_set - minimum) if accessed_set else max(0, accessed_count - required_covered)

        row["accessed_ids_count_norm"] = accessed_count
        row["required_count"] = len(minimum)
        row["required_covered_count"] = required_covered
        row["excess_access_count"] = excess
        row["required_coverage"] = required_covered / len(minimum) if minimum else 0.0
        row["access_precision"] = required_covered / accessed_count if accessed_count else 0.0
        row["task_success_num"] = 1 if row.get("task_success") else 0
        row["attack_exposure_num"] = 1 if row.get("attack_exposure") else 0
        row["attack_compliance_num"] = 1 if row.get("attack_compliance") else 0
        row["attack_leakage_num"] = 1 if row.get("attack_leakage") else 0
        row["malicious_accessed_count_norm"] = len(row.get("malicious_accessed", []) or [])
        normalized.append(row)

    return normalized


def deduplicate(rows: list[dict]) -> list[dict]:
    by_key = {}
    for row in rows:
        key = (row.get("model"), row.get("scenario"), row.get("condition"), row.get("seed"))
        by_key[key] = row
    return list(by_key.values())


def mean(rows: list[dict], key: str) -> float:
    vals = [float(r.get(key, 0) or 0) for r in rows]
    return sum(vals) / len(vals) if vals else 0.0


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return p, max(0.0, center - half), min(1.0, center + half)


def summarize_by(rows: list[dict], group_keys: tuple[str, ...]) -> list[dict]:
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(k) for k in group_keys)].append(row)

    summary = []
    for key, items in sorted(grouped.items()):
        success_count = sum(i["task_success_num"] for i in items)
        p, lo, hi = wilson_interval(success_count, len(items))
        record = {group_keys[i]: key[i] for i in range(len(group_keys))}
        record.update(
            {
                "n": len(items),
                "task_success_rate": p,
                "task_success_ci_low": lo,
                "task_success_ci_high": hi,
                "avg_accessed_ids": mean(items, "accessed_ids_count_norm"),
                "avg_excess_access": mean(items, "excess_access_count"),
                "avg_required_coverage": mean(items, "required_coverage"),
                "avg_access_precision": mean(items, "access_precision"),
                "attack_exposure_rate": mean(items, "attack_exposure_num"),
                "attack_compliance_rate": mean(items, "attack_compliance_num"),
                "attack_leakage_rate": mean(items, "attack_leakage_num"),
                "malicious_access_rate": mean(items, "malicious_accessed_count_norm"),
                "avg_latency_s": mean(items, "latency_s"),
                "avg_tool_calls": mean(items, "tool_call_count"),
            }
        )
        summary.append(record)
    return summary


def build_audit(raw_rows: list[dict], deduped_rows: list[dict], scenarios: list[dict]) -> dict:
    expected = {
        (m, s["id"], c, seed)
        for m in MODELS
        for s in scenarios
        for c in CONDITIONS
        for seed in SEEDS
    }
    observed_counter = Counter(
        (r.get("model"), r.get("scenario"), r.get("condition"), r.get("seed")) for r in raw_rows
    )
    observed = set(observed_counter)
    missing = expected - observed
    duplicate_groups = {str(k): n for k, n in observed_counter.items() if n > 1}

    group_expected = {(m, s["id"], c) for m in MODELS for s in scenarios for c in CONDITIONS}
    group_observed = {(r.get("model"), r.get("scenario"), r.get("condition")) for r in raw_rows}
    absent_groups = sorted(group_expected - group_observed, key=lambda x: (x[0], int(x[1][1:]), x[2]))

    return {
        "planned_runs": len(expected),
        "raw_rows": len(raw_rows),
        "unique_experiment_keys": len(deduped_rows),
        "missing_experiment_keys": len(missing),
        "duplicate_groups": len(duplicate_groups),
        "extra_duplicate_rows": len(raw_rows) - len(deduped_rows),
        "absent_model_scenario_condition_groups": [
            {"model": m, "scenario": s, "condition": c} for m, s, c in absent_groups
        ],
        "missing_by_model": dict(Counter(k[0] for k in missing)),
        "missing_by_condition": dict(Counter(k[2] for k in missing)),
        "missing_by_scenario": dict(Counter(k[1] for k in missing)),
    }


def plot_condition_effect(rows: list[dict]) -> Path:
    labels = CONDITIONS
    success = []
    coverage = []
    accessed = []
    excess = []
    for condition in labels:
        items = [r for r in rows if r.get("condition") == condition]
        success.append(mean(items, "task_success_num"))
        coverage.append(mean(items, "required_coverage"))
        accessed.append(mean(items, "accessed_ids_count_norm"))
        excess.append(mean(items, "excess_access_count"))

    x = list(range(len(labels)))
    width = 0.35
    fig, ax1 = plt.subplots(figsize=(8, 4.5))
    ax1.bar([i - width / 2 for i in x], success, width, label="task success", color="#4C78A8")
    ax1.bar([i + width / 2 for i in x], coverage, width, label="required coverage", color="#72B7B2")
    ax1.set_ylabel("rate")
    ax1.set_ylim(0, 0.45)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)
    ax1.legend(loc="upper left")

    ax2 = ax1.twinx()
    ax2.plot(x, accessed, marker="o", linewidth=2.2, color="#F58518", label="avg accessed IDs")
    ax2.plot(x, excess, marker="s", linewidth=2.2, color="#E45756", label="avg excess IDs")
    ax2.set_ylabel("avg IDs per run")
    ax2.set_ylim(0, max(2.0, max(accessed + excess) * 1.35))
    ax2.legend(loc="upper right")

    plt.title("Condition effect after deduplication")
    plt.tight_layout()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = FIG_DIR / "fig_condition_effect.png"
    plt.savefig(out, dpi=180)
    plt.close()
    return out


def plot_model_comparison(rows: list[dict]) -> Path:
    labels = MODELS
    success = []
    coverage = []
    accessed = []
    excess = []
    for model in labels:
        items = [r for r in rows if r.get("model") == model]
        success.append(mean(items, "task_success_num"))
        coverage.append(mean(items, "required_coverage"))
        accessed.append(mean(items, "accessed_ids_count_norm"))
        excess.append(mean(items, "excess_access_count"))

    x = list(range(len(labels)))
    width = 0.35
    fig, ax1 = plt.subplots(figsize=(8, 4.5))
    ax1.bar([i - width / 2 for i in x], success, width, label="task success", color="#4C78A8")
    ax1.bar([i + width / 2 for i in x], coverage, width, label="required coverage", color="#72B7B2")
    ax1.set_ylabel("rate")
    ax1.set_ylim(0, 0.45)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=12)
    ax1.legend(loc="upper left")

    ax2 = ax1.twinx()
    ax2.plot(x, accessed, marker="o", linewidth=2.2, color="#F58518", label="avg accessed IDs")
    ax2.plot(x, excess, marker="s", linewidth=2.2, color="#E45756", label="avg excess IDs")
    ax2.set_ylabel("avg IDs per run")
    ax2.set_ylim(0, max(2.0, max(accessed + excess) * 1.35))
    ax2.legend(loc="upper right")

    plt.title("Model comparison after deduplication")
    plt.tight_layout()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = FIG_DIR / "fig_model_compare_v2.png"
    plt.savefig(out, dpi=180)
    plt.close()
    return out


def plot_completion_matrix(raw_rows: list[dict], scenarios: list[dict]) -> Path:
    counts = Counter((r.get("model"), r.get("scenario"), r.get("condition")) for r in raw_rows)
    model_short = {"qwen3:8b": "Q3", "llama3.1:8b": "L3.1", "qwen2.5:7b": "Q2.5"}
    group_labels = [f"{model_short.get(m, m)}-{c}" for m in MODELS for c in CONDITIONS]
    scenario_ids = [s["id"] for s in scenarios]
    matrix = [
        [counts.get((m, s, c), 0) for m in MODELS for c in CONDITIONS]
        for s in scenario_ids
    ]

    fig, ax = plt.subplots(figsize=(11, 5.4))
    im = ax.imshow(matrix, cmap="YlGnBu", vmin=0, vmax=10)
    ax.set_xticks(range(len(group_labels)))
    ax.set_xticklabels(group_labels, fontsize=9, rotation=25, ha="right")
    ax.set_yticks(range(len(scenario_ids)))
    ax.set_yticklabels(scenario_ids)
    ax.set_title("Completed raw runs per scenario/model/condition")
    for y, row in enumerate(matrix):
        for x, val in enumerate(row):
            ax.text(x, y, str(val), ha="center", va="center", fontsize=7, color="#111")
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label("raw rows")
    plt.tight_layout()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = FIG_DIR / "fig_completion_matrix_v2.png"
    plt.savefig(out, dpi=180)
    plt.close()
    return out


def main() -> None:
    scenarios = load_scenarios()
    raw_rows = normalize_runs(load_runs(), scenarios)
    if not raw_rows:
        raise SystemExit("No v2 runs found.")

    deduped_rows = deduplicate(raw_rows)
    audit = build_audit(raw_rows, deduped_rows, scenarios)
    summary = {
        "audit": audit,
        "dedup_by_condition": summarize_by(deduped_rows, ("condition",)),
        "dedup_by_model": summarize_by(deduped_rows, ("model",)),
        "dedup_by_model_condition": summarize_by(deduped_rows, ("model", "condition")),
        "dedup_by_scenario": summarize_by(deduped_rows, ("scenario",)),
        "raw_by_model_condition_scenario": summarize_by(raw_rows, ("model", "condition", "scenario")),
    }

    with SUMMARY_JSON.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with AUDIT_JSON.open("w", encoding="utf-8") as f:
        json.dump(audit, f, ensure_ascii=False, indent=2)

    fig1 = plot_condition_effect(deduped_rows)
    fig2 = plot_model_comparison(deduped_rows)
    fig3 = plot_completion_matrix(raw_rows, scenarios)

    print(json.dumps(audit, ensure_ascii=False, indent=2))
    print("Figures:")
    print(fig1)
    print(fig2)
    print(fig3)
    print("Summary:", SUMMARY_JSON)


if __name__ == "__main__":
    main()
