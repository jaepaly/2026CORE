#!/usr/bin/env python3
"""v2 실험 결과 분석: 표/그림 생성 + 요약 JSON (20 시나리오, D 조건 포함)."""
import os
import json
import math
import os
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
FIG_DIR = os.path.join(os.path.dirname(__file__), "docs", "figures")
RESULTS_JSON = os.path.join(OUTPUT_DIR, "multi_model_results_v2.json")
SUMMARY_JSON = os.path.join(OUTPUT_DIR, "analysis_summary_v2.json")


def load_scenarios():
    path = os.path.join(DATA_DIR, "scenarios_v2.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {s["id"]: s for s in data["scenarios"]}


def v2_run_files():
    """모든 모델의 v2 런 파일(runs_*.jsonl). runs.jsonl(옛 혼합)·runs_v3_*(보조) 제외."""
    import glob
    out = []
    for p in sorted(glob.glob(os.path.join(OUTPUT_DIR, "runs_*.jsonl"))):
        base = os.path.basename(p)
        if base == "runs.jsonl" or base.startswith("runs_v3_"):
            continue
        out.append(p)
    return out


def load_runs():
    rows = []
    for path in v2_run_files():
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    return rows


def compute_precision_excess(rows, scenarios):
    """접근 정밀도와 초과 접근을 계산."""
    enriched = []
    for r in rows:
        sid = r.get("scenario")
        accessed = r.get("accessed_ids", [])
        minimum = scenarios.get(sid, {}).get("minimum", [])
        minimum_set = set(minimum)
        accessed_set = set(accessed)
        essential_hits = len(accessed_set & minimum_set)
        excess = len(accessed_set - minimum_set)
        precision = essential_hits / len(accessed_set) if accessed_set else 0.0
        r["accessed_ids_count"] = len(accessed_set)
        r["essential_hits"] = essential_hits
        r["excess_access"] = excess
        r["access_precision"] = precision
        enriched.append(r)
    return enriched


def aggregate(rows):
    grouped = defaultdict(list)
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
    for (model, condition, scenario), items in grouped.items():
        def mean(k):
            vals = [i.get(k) for i in items if isinstance(i.get(k), (int, float))]
            return sum(vals) / len(vals) if vals else 0.0

        def rate(k):
            vals = [i.get(k) for i in items if isinstance(i.get(k), (int, float))]
            return sum(vals) / len(vals) if vals else 0.0

        summary.append({
            "model": model,
            "condition": condition,
            "scenario": scenario,
            "task_success_rate": rate("task_success"),
            "avg_accessed_ids": mean("accessed_ids_count"),
            "access_precision": mean("access_precision"),
            "excess_access": mean("excess_access"),
            "attack_exposure_rate": rate("attack_exposure") if "attack_exposure" in items[0] else 0.0,
            "attack_compliance_rate": rate("attack_compliance") if "attack_compliance" in items[0] else 0.0,
            "attack_leakage_rate": rate("attack_leakage") if "attack_leakage" in items[0] else 0.0,
            "avg_latency_s": mean("latency_s"),
            "avg_tool_calls": mean("tool_call_count"),
            "n": len(items),
        })
    return summary


def plot_condition_effect(rows):
    conds = ["A", "B", "C", "D"]
    success_by_cond = {c: [] for c in conds}
    access_by_cond = {c: [] for c in conds}
    precision_by_cond = {c: [] for c in conds}
    excess_by_cond = {c: [] for c in conds}
    for r in rows:
        c = r.get("condition")
        if c not in conds:
            continue
        success_by_cond[c].append(1 if r.get("task_success") else 0)
        access_by_cond[c].append(r.get("accessed_ids_count", 0))
        precision_by_cond[c].append(r.get("access_precision", 0))
        excess_by_cond[c].append(r.get("excess_access", 0))

    labels = conds
    x = range(len(labels))
    fig, ax1 = plt.subplots(figsize=(8, 4))
    width = 0.2
    success_means = [sum(success_by_cond[c]) / len(success_by_cond[c]) if success_by_cond[c] else 0 for c in labels]
    precision_means = [sum(precision_by_cond[c]) / len(precision_by_cond[c]) if precision_by_cond[c] else 0 for c in labels]
    excess_means = [sum(excess_by_cond[c]) / len(excess_by_cond[c]) if excess_by_cond[c] else 0 for c in labels]
    access_means = [sum(access_by_cond[c]) / len(access_by_cond[c]) if access_by_cond[c] else 0 for c in labels]

    ax1.bar([i - width for i in x], success_means, width, label="task_success", color="#4C78A8")
    ax1.bar(x, precision_means, width, label="access_precision", color="#54A24B")
    ax1.bar([i + width for i in x], excess_means, width, label="excess_access", color="#E45756")
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
    ax1.legend(loc="upper left")
    ax2 = ax1.twinx()
    ax2.plot(x, access_means, marker="o", color="#F58518", label="accessed_ids")
    ax2.set_ylabel("avg accessed IDs")
    ax2.legend(loc="upper right")
    plt.title("Condition effect (D added)")
    plt.tight_layout()
    os.makedirs(FIG_DIR, exist_ok=True)
    out = os.path.join(FIG_DIR, "fig_condition_effect.png")
    plt.savefig(out, dpi=160)
    plt.close()
    return out


def plot_model_comparison(rows):
    models = ["qwen3:8b", "llama3.1:8b", "qwen2.5:7b"]
    success_by_model = {m: [] for m in models}
    access_by_model = {m: [] for m in models}
    precision_by_model = {m: [] for m in models}
    excess_by_model = {m: [] for m in models}
    for r in rows:
        m = r.get("model")
        if m not in models:
            continue
        success_by_model[m].append(1 if r.get("task_success") else 0)
        access_by_model[m].append(r.get("accessed_ids_count", 0))
        precision_by_model[m].append(r.get("access_precision", 0))
        excess_by_model[m].append(r.get("excess_access", 0))

    success = [sum(success_by_model[m]) / len(success_by_model[m]) if success_by_model[m] else 0 for m in models]
    access = [sum(access_by_model[m]) / len(access_by_model[m]) if access_by_model[m] else 0 for m in models]
    precision = [sum(precision_by_model[m]) / len(precision_by_model[m]) if precision_by_model[m] else 0 for m in models]
    excess = [sum(excess_by_model[m]) / len(excess_by_model[m]) if excess_by_model[m] else 0 for m in models]

    fig, ax1 = plt.subplots(figsize=(8, 4))
    x = range(len(models))
    width = 0.2
    ax1.bar([i - width for i in x], success, width, label="task_success", color="#4C78A8")
    ax1.bar(x, precision, width, label="access_precision", color="#54A24B")
    ax1.bar([i + width for i in x], excess, width, label="excess_access", color="#E45756")
    ax1.set_xticks(x)
    ax1.set_xticklabels(models, rotation=15)
    ax1.set_ylim(0, 1.05)
    ax1.set_ylabel("rate")
    ax1.legend(loc="upper left")
    ax2 = ax1.twinx()
    ax2.plot(x, access, marker="o", color="#F58518", label="accessed_ids")
    ax2.set_ylabel("avg accessed IDs")
    ax2.legend(loc="upper right")
    plt.title("Model comparison (D added)")
    plt.tight_layout()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = FIG_DIR / "fig_model_compare_v2.png"
    plt.savefig(out, dpi=180)
    plt.close()
    return out


def print_summary(rows):
    by_model_cond = defaultdict(list)
    for r in rows:
        by_model_cond[(r.get("model"), r.get("condition"))].append(r)
    print(f"Total runs: {len(rows)}")
    print("model | condition | success_rate | avg_accessed | precision | excess | attack_exp")
    for (m, c), items in sorted(by_model_cond.items()):
        succ = sum(1 for i in items if i.get("task_success")) / len(items)
        acc = sum(i.get("accessed_ids_count", 0) for i in items) / len(items)
        prec = sum(i.get("access_precision", 0) for i in items) / len(items)
        exc = sum(i.get("excess_access", 0) for i in items) / len(items)
        exp = sum(1 for i in items if i.get("attack_exposure")) / len(items)
        print(f"{m} | {c} | {succ:.3f} | {acc:.2f} | {prec:.3f} | {exc:.2f} | {exp:.2f}")


def main():
    rows = load_runs()
    if not rows:
        print("No runs found.")
        return
    scenarios = load_scenarios()
    rows = compute_precision_excess(rows, scenarios)
    summary = aggregate(rows)
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    fig1 = plot_condition_effect(rows)
    fig2 = plot_model_comparison(rows)
    print_summary(rows)
    print("Figures:", fig1, fig2)
    print("Results:", RESULTS_JSON)


if __name__ == "__main__":
    main()
