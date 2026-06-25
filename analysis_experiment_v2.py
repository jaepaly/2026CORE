#!/usr/bin/env python3
"""v2 실험 결과 분석: 표/그림 생성 + 요약 JSON."""
import os
import json
import math
from collections import defaultdict
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
FIG_DIR = os.path.join(os.path.dirname(__file__), "docs", "figures")
RUNS_JSONL = os.path.join(OUTPUT_DIR, "runs.jsonl")
RESULTS_JSON = os.path.join(OUTPUT_DIR, "multi_model_results_v2.json")
SUMMARY_JSON = os.path.join(OUTPUT_DIR, "analysis_summary_v2.json")


def load_runs():
    rows = []
    if not os.path.exists(RUNS_JSONL):
        return rows
    with open(RUNS_JSONL, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def aggregate(rows):
    # model x condition
    grouped = defaultdict(list)
    for r in rows:
        key = (r.get("model"), r.get("condition"), r.get("scenario"))
        grouped[key].append(r)
    summary = []
    for (model, condition, scenario), items in grouped.items():
        def mean(k):
            vals = [i.get(k) for i in items if isinstance(i.get(k), (int, float))]
            return sum(vals) / len(vals) if vals else 0.0
        summary.append({
            "model": model,
            "condition": condition,
            "scenario": scenario,
            "task_success_rate": mean("task_success"),
            "avg_accessed_ids": mean("accessed_ids_count"),
            "attack_exposure_rate": mean("attack_exposure") if "attack_exposure" in items[0] else 0.0,
            "attack_compliance_rate": mean("attack_compliance") if "attack_compliance" in items[0] else 0.0,
            "attack_leakage_rate": mean("attack_leakage") if "attack_leakage" in items[0] else 0.0,
            "avg_latency_s": mean("latency_s"),
            "avg_tool_calls": mean("tool_call_count"),
            "n": len(items),
        })
    return summary


def mean_ci(vals):
    m = sum(vals) / len(vals) if vals else 0.0
    if len(vals) < 2:
        return m, 0.0, 0.0
    se = (sum((x - m) ** 2 for x in vals) / (len(vals) - 1)) ** 0.5 * (1 / math.sqrt(len(vals)))
    return m, max(0, m - 1.96 * se), min(1, m + 1.96 * se)


def plot_condition_effect(rows):
    # 조건별 성공률 / 평균 접근 수 (모델 무관)
    conds = ["A", "B", "C"]
    success_by_cond = {c: [] for c in conds}
    access_by_cond = {c: [] for c in conds}
    attack_by_cond = {c: [] for c in conds}
    for r in rows:
        c = r.get("condition")
        if c not in conds:
            continue
        success_by_cond[c].append(1 if r.get("task_success") else 0)
        access_by_cond[c].append(r.get("accessed_ids_count", 0))
        attack_by_cond[c].append(1 if r.get("attack_exposure") else 0)

    labels = conds
    x = range(len(labels))
    fig, ax1 = plt.subplots(figsize=(7, 4))
    width = 0.25
    success_means = [sum(success_by_cond[c]) / len(success_by_cond[c]) if success_by_cond[c] else 0 for c in labels]
    attack_means = [sum(attack_by_cond[c]) / len(attack_by_cond[c]) if attack_by_cond[c] else 0 for c in labels]
    access_means = [sum(access_by_cond[c]) / len(access_by_cond[c]) if access_by_cond[c] else 0 for c in labels]
    ax1.bar([i - width for i in x], success_means, width, label="task_success", color="#4C78A8")
    ax1.bar(x, attack_means, width, label="attack_exposure", color="#E45756")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)
    ax1.set_ylim(0, 1.05)
    ax1.set_ylabel("rate")
    ax1.legend(loc="upper left")
    ax2 = ax1.twinx()
    ax2.plot(x, access_means, marker="o", color="#F58518", label="accessed_ids")
    ax2.set_ylabel("avg accessed IDs")
    ax2.legend(loc="upper right")
    plt.title("Condition effect (task success, attack exposure, accessed IDs)")
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
    for r in rows:
        m = r.get("model")
        if m not in models:
            continue
        success_by_model[m].append(1 if r.get("task_success") else 0)
        access_by_model[m].append(r.get("accessed_ids_count", 0))
    success = [sum(success_by_model[m]) / len(success_by_model[m]) if success_by_model[m] else 0 for m in models]
    access = [sum(access_by_model[m]) / len(access_by_model[m]) if access_by_model[m] else 0 for m in models]
    fig, ax1 = plt.subplots(figsize=(7, 4))
    x = range(len(models))
    ax1.bar(x, success, color="#4C78A8", label="task_success")
    ax1.set_xticks(x)
    ax1.set_xticklabels(models, rotation=15)
    ax1.set_ylim(0, 1.05)
    ax1.set_ylabel("task_success_rate")
    ax2 = ax1.twinx()
    ax2.plot(x, access, marker="o", color="#F58518", label="accessed_ids")
    ax2.set_ylabel("avg accessed IDs")
    ax2.legend(loc="upper right")
    ax1.legend(loc="upper left")
    plt.title("Model comparison")
    plt.tight_layout()
    os.makedirs(FIG_DIR, exist_ok=True)
    out = os.path.join(FIG_DIR, "fig_model_compare_v2.png")
    plt.savefig(out, dpi=160)
    plt.close()
    return out


def main():
    rows = load_runs()
    if not rows:
        print("No runs found.")
        return
    summary = aggregate(rows)
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    fig1 = plot_condition_effect(rows)
    fig2 = plot_model_comparison(rows)
    # print summary
    by_model_cond = defaultdict(list)
    for r in rows:
        by_model_cond[(r.get("model"), r.get("condition"))].append(r)
    print(f"Total runs: {len(rows)}")
    print("model | condition | success_rate | avg_accessed | attack_exposure")
    for (m, c), items in sorted(by_model_cond.items()):
        succ = sum(1 for i in items if i.get("task_success")) / len(items)
        acc = sum(i.get("accessed_ids_count", 0) for i in items) / len(items)
        exp = sum(1 for i in items if i.get("attack_exposure")) / len(items)
        print(f"{m} | {c} | {succ:.2f} | {acc:.2f} | {exp:.2f}")
    print("Figures:", fig1, fig2)
    print("Results:", RESULTS_JSON)


if __name__ == "__main__":
    main()
