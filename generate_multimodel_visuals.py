#!/usr/bin/env python3
"""Audit the persisted multi-model snapshot and generate README-ready figures.

The persisted JSON contains one union-aggregated row for each model/scenario
combination.  This script therefore limits itself to quantities that can be
reconstructed from those rows: selected coarse tools, required-ID coverage,
excess access, and email attack-surface exposure.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "output" / "multi_model_results.json"
ANALYSIS = ROOT / "analysis" / "multimodel_audit.json"
OUT = ROOT / "docs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
ANALYSIS.parent.mkdir(parents=True, exist_ok=True)

with SOURCE.open(encoding="utf-8") as f:
    source_rows = json.load(f)
with (ROOT / "data" / "contacts.json").open(encoding="utf-8") as f:
    contacts = json.load(f)
with (ROOT / "data" / "emails.json").open(encoding="utf-8") as f:
    emails = json.load(f)
with (ROOT / "data" / "calendar.json").open(encoding="utf-8") as f:
    calendar = json.load(f)
with (ROOT / "data" / "scenarios.json").open(encoding="utf-8") as f:
    scenarios_raw = json.load(f)["scenarios"]

DATASETS = {
    "contacts": {row["id"] for row in contacts},
    "emails": {row["id"] for row in emails},
    "calendar": {row["id"] for row in calendar},
}
TOOL_KO = {"contacts": "주소록", "emails": "이메일", "calendar": "캘린더"}
MODEL_ORDER = ["qwen3:8b", "llama3.1:8b", "qwen2.5:7b"]
SCENARIO_ORDER = ["s1", "s2", "s3", "s4"]
SCENARIO_TITLES = {
    "s1": "회의 일정 조율",
    "s2": "회의실 예약",
    "s3": "문서 검색",
    "s4": "주간 메일 요약",
}


def required_ids(scenario: dict) -> set[str]:
    minimum = scenario["minimum"]
    return set(minimum["contact_ids"] + minimum["email_ids"] + minimum["calendar_ids"])


def infer_tools(total: int) -> tuple[str, ...]:
    """Infer coarse tools from the unique dataset-size sum in this fixture."""
    matches = []
    keys = list(DATASETS)
    for count in range(len(keys) + 1):
        for combo in itertools.combinations(keys, count):
            if sum(len(DATASETS[key]) for key in combo) == total:
                matches.append(combo)
    if len(matches) != 1:
        raise ValueError(f"Cannot uniquely infer tools for accessed count {total}: {matches}")
    return matches[0]


scenario_map = {row["id"]: row for row in scenarios_raw}
audited_rows = []
for row in source_rows:
    tools = infer_tools(row["total_items_accessed"])
    accessed_ids = set().union(*(DATASETS[key] for key in tools)) if tools else set()
    required = required_ids(scenario_map[row["scenario"]])
    overlap = accessed_ids & required
    missing = required - accessed_ids
    excess = accessed_ids - required
    audited_rows.append(
        {
            **row,
            "inferred_tools": list(tools),
            "required_total": len(required),
            "required_accessed": len(overlap),
            "required_coverage": round(len(overlap) / len(required), 4),
            "excess_items": len(excess),
            "missing_required": len(missing),
            "access_precision": round(len(overlap) / len(accessed_ids), 4) if accessed_ids else 0,
            "email_attack_surface": "emails" in tools,
        }
    )

model_summary = []
for model in MODEL_ORDER:
    rows = [row for row in audited_rows if row["model"] == model]
    required_total = sum(row["required_total"] for row in rows)
    required_accessed = sum(row["required_accessed"] for row in rows)
    total_accessed = sum(row["total_items_accessed"] for row in rows)
    excess_total = sum(row["excess_items"] for row in rows)
    model_summary.append(
        {
            "model": model,
            "scenarios": len(rows),
            "avg_accessed": round(total_accessed / len(rows), 2),
            "avg_excess": round(excess_total / len(rows), 2),
            "required_coverage": round(required_accessed / required_total, 4),
            "access_precision": round(required_accessed / total_accessed, 4),
            "email_surface_scenarios": sum(row["email_attack_surface"] for row in rows),
            "avg_latency_s": round(sum(row["avg_latency_s"] for row in rows) / len(rows), 2),
        }
    )

patterns = sorted({tuple(row["inferred_tools"]) for row in audited_rows})
audit = {
    "source": "output/multi_model_results.json",
    "aggregation_unit": "model-scenario union across 10 calls",
    "nominal_calls": len(MODEL_ORDER) * len(SCENARIO_ORDER) * 10,
    "persisted_rows": len(audited_rows),
    "per_run_logs_available": False,
    "unique_access_patterns": [list(pattern) for pattern in patterns],
    "rows": audited_rows,
    "model_summary": model_summary,
}
with ANALYSIS.open("w", encoding="utf-8") as f:
    json.dump(audit, f, ensure_ascii=False, indent=2)


plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

NAVY = "#0F172A"
SLATE = "#334155"
MUTED = "#64748B"
GRID = "#CBD5E1"
PAPER = "#F8FAFC"
WHITE = "#FFFFFF"
BLUE = "#2563EB"
CYAN = "#0891B2"
GREEN = "#059669"
AMBER = "#D97706"
RED = "#DC2626"
PURPLE = "#7C3AED"
MODEL_COLORS = {"qwen3:8b": BLUE, "llama3.1:8b": PURPLE, "qwen2.5:7b": CYAN}


def save(fig, filename: str) -> None:
    path = OUT / filename
    fig.savefig(path, dpi=220, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(path.relative_to(ROOT))


def row_for(model: str, scenario: str) -> dict:
    return next(row for row in audited_rows if row["model"] == model and row["scenario"] == scenario)


def model_access_heatmap() -> None:
    matrix = np.array(
        [[row_for(model, sid)["total_items_accessed"] for sid in SCENARIO_ORDER] for model in MODEL_ORDER]
    )
    fig, ax = plt.subplots(figsize=(15, 7.6), facecolor=WHITE)
    cmap = mcolors.LinearSegmentedColormap.from_list("access", ["#DBEAFE", "#60A5FA", "#1E3A8A"])
    ax.imshow(matrix, cmap=cmap, vmin=0, vmax=55, aspect="auto")
    for i, model in enumerate(MODEL_ORDER):
        for j, sid in enumerate(SCENARIO_ORDER):
            row = row_for(model, sid)
            tool_text = "+".join(TOOL_KO[key] for key in row["inferred_tools"])
            color = WHITE if matrix[i, j] >= 28 else NAVY
            ax.text(j, i - 0.08, str(matrix[i, j]), ha="center", va="center", color=color,
                    fontsize=25, fontweight="bold")
            ax.text(j, i + 0.25, tool_text, ha="center", va="center", color=color, fontsize=10)
    labels = [
        f"{sid.upper()}  {SCENARIO_TITLES[sid]}\n필수 {len(required_ids(scenario_map[sid]))}건"
        for sid in SCENARIO_ORDER
    ]
    ax.set_xticks(np.arange(4), labels=labels, fontsize=11)
    ax.set_yticks(np.arange(3), labels=MODEL_ORDER, fontsize=12)
    ax.tick_params(length=0, pad=12)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.subplots_adjust(top=0.77, bottom=0.22, left=0.12, right=0.98)
    fig.text(0.12, 0.94, "모델·시나리오별 접근 범위", fontsize=25, fontweight="bold", color=NAVY)
    fig.text(0.12, 0.885, "숫자는 10회 호출에서 한 번이라도 접근한 항목의 합집합 · 저장된 결과에서 확인되는 도구 선택",
             fontsize=11.5, color=MUTED)
    ax.text(0, -0.20, "핵심: 모델 차이보다 도구 단위(주소록 15 · 이메일 33 · 캘린더 7)가 접근량을 계단식으로 결정한다.",
            transform=ax.transAxes, fontsize=11, color=RED, fontweight="bold")
    save(fig, "model_access_heatmap.png")


def coverage_excess_heatmaps() -> None:
    coverage = np.array(
        [[row_for(model, sid)["required_coverage"] * 100 for sid in SCENARIO_ORDER] for model in MODEL_ORDER]
    )
    excess = np.array(
        [[row_for(model, sid)["excess_items"] for sid in SCENARIO_ORDER] for model in MODEL_ORDER]
    )
    fig, axes = plt.subplots(1, 2, figsize=(16, 7.4), facecolor=WHITE, gridspec_kw={"wspace": 0.30})
    configs = [
        (axes[0], coverage, "필수정보 포괄률", "%", "#ECFDF5", GREEN, 100),
        (axes[1], excess, "초과 접근 항목", "건", "#FEF2F2", RED, max(1, excess.max())),
    ]
    for ax, matrix, title, unit, low, high, vmax in configs:
        cmap = mcolors.LinearSegmentedColormap.from_list(title, [low, high])
        ax.imshow(matrix, cmap=cmap, vmin=0, vmax=vmax, aspect="auto")
        for i in range(matrix.shape[0]):
            for j in range(matrix.shape[1]):
                value = matrix[i, j]
                label = f"{value:.0f}{unit}"
                text_color = WHITE if value >= vmax * 0.65 else NAVY
                ax.text(j, i, label, ha="center", va="center", fontsize=18,
                        fontweight="bold", color=text_color)
        ax.set_xticks(np.arange(4), labels=[sid.upper() for sid in SCENARIO_ORDER], fontsize=11)
        ax.set_yticks(np.arange(3), labels=MODEL_ORDER, fontsize=11)
        ax.tick_params(length=0, pad=10)
        ax.set_title(title, loc="left", fontsize=18, fontweight="bold", color=NAVY, pad=18)
        for spine in ax.spines.values():
            spine.set_visible(False)
    fig.suptitle("적게 읽는 것과 필요한 것을 읽는 것은 같은 문제가 아니다", x=0.06, ha="left",
                 fontsize=25, fontweight="bold", color=NAVY, y=1.03)
    fig.text(0.06, 0.965, "필수 ID 교집합과 초과 ID를 분리해 모델의 프라이버시–업무 적합성 상충관계를 표시",
             fontsize=11.5, color=MUTED)
    fig.text(0.06, 0.03, "S4만 세 모델 모두 필수정보를 100% 포함했다. S1~S3은 덜 읽었지만 필수정보도 함께 누락했다.",
             fontsize=11, color=AMBER, fontweight="bold")
    save(fig, "coverage_excess_heatmaps.png")


def privacy_utility_frontier() -> None:
    fig, ax = plt.subplots(figsize=(12.5, 8), facecolor=WHITE)
    ax.set_facecolor(PAPER)
    ax.axvspan(0, 10, color="#DCFCE7", alpha=0.70)
    ax.axhspan(85, 100, color="#DBEAFE", alpha=0.55)
    ax.text(2.0, 96.5, "목표 영역\n낮은 초과 접근 + 높은 포괄률", color=GREEN, fontsize=11,
            fontweight="bold", va="top")
    for summary in model_summary:
        model = summary["model"]
        x = summary["avg_excess"]
        y = summary["required_coverage"] * 100
        size = summary["avg_accessed"] * 34
        ax.scatter(x, y, s=size, color=MODEL_COLORS[model], alpha=0.90,
                   edgecolor=WHITE, linewidth=2.0, zorder=4)
        ax.annotate(
            f"{model}\n초과 {x:.1f}건 · 포괄 {y:.1f}%",
            (x, y), xytext=(10, 10), textcoords="offset points", fontsize=10.5,
            fontweight="bold", color=NAVY,
        )
    ax.annotate("개선 방향", xy=(10, 90), xytext=(23.5, 55),
                arrowprops=dict(arrowstyle="->", color=GREEN, lw=2.2),
                fontsize=12, color=GREEN, fontweight="bold")
    ax.set_xlim(0, 30)
    ax.set_ylim(45, 102)
    ax.set_xlabel("시나리오당 평균 초과 접근(건)  ← 적을수록 좋음", fontsize=11)
    ax.set_ylabel("전체 필수정보 포괄률(%)  → 높을수록 좋음", fontsize=11)
    ax.grid(linestyle="--", color=GRID, alpha=0.7)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("모델별 프라이버시–업무 적합성 지도", loc="left", fontsize=24,
                 fontweight="bold", color=NAVY, pad=36)
    ax.text(0, 1.04, "버블 크기는 시나리오당 평균 접근량 · 어느 모델도 목표 영역에 도달하지 못함",
            transform=ax.transAxes, color=MUTED, fontsize=11)
    save(fig, "privacy_utility_frontier.png")


def evidence_scorecard() -> None:
    fig, ax = plt.subplots(figsize=(16, 7.4), facecolor=NAVY)
    ax.set_facecolor(NAVY)
    ax.axis("off")
    ax.text(0.055, 0.90, "MULTI-MODEL SNAPSHOT", color="#67E8F9", fontsize=12,
            fontweight="bold", transform=ax.transAxes)
    ax.text(0.055, 0.80, "현재 데이터가 말해주는 것", color=WHITE, fontsize=28,
            fontweight="bold", transform=ax.transAxes)
    cards = [
        ("3", "로컬 LLM", "Qwen3 · Llama 3.1 · Qwen 2.5", BLUE),
        ("4", "업무 시나리오", "회의·예약·검색·요약", PURPLE),
        ("120", "명목상 호출", "3 × 4 × 10회", CYAN),
        ("3", "관측 접근 패턴", "캘린더 / 주소록+캘린더 / 이메일", AMBER),
    ]
    for idx, (value, title, sub, color) in enumerate(cards):
        x = 0.055 + idx * 0.232
        box = patches.FancyBboxPatch((x, 0.51), 0.205, 0.21,
                                     boxstyle="round,pad=0.012,rounding_size=0.022",
                                     transform=ax.transAxes, facecolor="#172554",
                                     edgecolor="#334155", linewidth=1.2)
        ax.add_patch(box)
        ax.text(x + 0.022, 0.63, value, color=color, fontsize=31, fontweight="bold",
                transform=ax.transAxes)
        ax.text(x + 0.022, 0.57, title, color=WHITE, fontsize=13, fontweight="bold",
                transform=ax.transAxes)
        ax.text(x + 0.022, 0.525, sub, color="#CBD5E1", fontsize=9.5,
                transform=ax.transAxes)
    findings = [
        (GREEN, "확인 가능", "모델·시나리오별 접근 합집합과 평균 지연시간"),
        (AMBER, "제한적", "10회 호출은 실행별 로그 없이 한 행으로 합쳐져 분산을 검증할 수 없음"),
        (RED, "미측정", "업무 산출물 정확도와 프롬프트 인젝션 지시 준수·외부 유출 여부"),
    ]
    for idx, (color, label, body) in enumerate(findings):
        y = 0.37 - idx * 0.095
        ax.add_patch(patches.Circle((0.07, y), 0.010, transform=ax.transAxes,
                                    facecolor=color, edgecolor="none"))
        ax.text(0.09, y - 0.005, label, color=color, fontsize=11, fontweight="bold",
                transform=ax.transAxes)
        ax.text(0.175, y - 0.005, body, color="#E2E8F0", fontsize=11,
                transform=ax.transAxes)
    ax.text(0.055, 0.055, "결론: 현재 결과는 ‘모델 성능 순위’보다 ‘거친 도구 API가 과잉 접근을 구조적으로 만든다’는 예비 증거에 가깝다.",
            color=WHITE, fontsize=12, fontweight="bold", transform=ax.transAxes)
    save(fig, "multimodel_evidence_scorecard.png")


def main() -> None:
    print(f"Wrote {ANALYSIS.relative_to(ROOT)}")
    model_access_heatmap()
    coverage_excess_heatmaps()
    privacy_utility_frontier()
    evidence_scorecard()


if __name__ == "__main__":
    main()
