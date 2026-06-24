#!/usr/bin/env python3
"""Generate polished, evidence-aligned visuals for the over-access README."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parent
SUMMARY_PATH = ROOT / "analysis" / "audit_summary.json"
OUT = ROOT / "docs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

if not SUMMARY_PATH.exists():
    import audit_experiment

    audit_experiment.main()

with SUMMARY_PATH.open(encoding="utf-8") as f:
    summary = json.load(f)

conditions = summary["s1_conditions"]

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


def save(fig, name: str):
    path = OUT / name
    fig.savefig(path, dpi=220, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"- {path.relative_to(ROOT)}")


def rounded_box(ax, xy, width, height, facecolor, edgecolor="none", radius=0.025, lw=1.2):
    box = patches.FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle=f"round,pad=0.012,rounding_size={radius}",
        transform=ax.transAxes,
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=lw,
    )
    ax.add_patch(box)
    return box


def condition_values():
    ordered = ["전체 접근 (A)", "최소정보 오라클 (B)", "Qwen3 스냅샷 (C)"]
    return [(label, conditions[label]) for label in ordered]


def hero():
    fig, ax = plt.subplots(figsize=(16, 6.4))
    fig.patch.set_facecolor(NAVY)
    ax.set_facecolor(NAVY)
    ax.axis("off")

    ax.text(0.055, 0.955, "PRIVACY × AGENTIC AI", color="#67E8F9", fontsize=12, fontweight="bold", transform=ax.transAxes)
    ax.text(0.055, 0.72, "AI 에이전트는 일을 위해\n얼마나 많은 개인정보를 읽는가?", color=WHITE, fontsize=29, fontweight="bold", transform=ax.transAxes, linespacing=1.13)
    ax.text(0.055, 0.54, "도구 사용형 에이전트의 필수 접근·초과 접근·공격표면을 분리 측정하는 시뮬레이터 기반 연구", color="#CBD5E1", fontsize=12.5, transform=ax.transAxes)

    card_x = [0.055, 0.37, 0.685]
    card_colors = ["#3F1D2B", "#103A35", "#3A2B16"]
    accents = [RED, GREEN, AMBER]
    titles = ["전체 접근 A", "최소정보 B", "Qwen3 스냅샷 C"]
    subtitles = ["모든 도구 데이터 제공", "정답 ID를 제공한 오라클", "연락처·캘린더 도구 선택"]

    for x, bg, accent, title, subtitle, (_, result) in zip(card_x, card_colors, accents, titles, subtitles, condition_values()):
        rounded_box(ax, (x, 0.13), 0.27, 0.31, bg, radius=0.025)
        ax.add_patch(patches.Rectangle((x, 0.13), 0.009, 0.31, transform=ax.transAxes, facecolor=accent, edgecolor="none"))
        ax.text(x + 0.025, 0.385, title, color=WHITE, fontsize=14, fontweight="bold", transform=ax.transAxes)
        ax.text(x + 0.025, 0.345, subtitle, color="#CBD5E1", fontsize=9.5, transform=ax.transAxes)
        ax.text(x + 0.025, 0.235, f"{result['accessed']}", color=WHITE, fontsize=30, fontweight="bold", transform=ax.transAxes)
        ax.text(x + 0.085, 0.248, "개 접근", color="#CBD5E1", fontsize=10, transform=ax.transAxes)
        precision = result["required_accessed"] / result["accessed"] * 100 if result["accessed"] else 0
        ax.text(x + 0.165, 0.252, f"정밀도 {precision:.1f}%", color=accent, fontsize=11, fontweight="bold", transform=ax.transAxes)
        ax.text(x + 0.025, 0.175, f"초과 {result['excess_items']}개  ·  필수정보 포괄률 {result['required_coverage']*100:.0f}%", color="#E2E8F0", fontsize=10.5, transform=ax.transAxes)

    ax.text(0.055, 0.055, "S1 회의 일정 조율 · 합성 개인정보 55개 · B는 이론적 상한선, C는 저장된 접근 스냅샷", color="#94A3B8", fontsize=9.5, transform=ax.transAxes)
    save(fig, "readme_hero.png")


def method_diagram():
    fig, ax = plt.subplots(figsize=(16, 7.5))
    fig.patch.set_facecolor(PAPER)
    ax.set_facecolor(PAPER)
    ax.axis("off")

    ax.text(0.05, 0.91, "연구 설계", fontsize=25, fontweight="bold", color=NAVY, transform=ax.transAxes)
    ax.text(0.05, 0.855, "동일 업무에서 데이터 제공 범위가 접근 행태와 개인정보 노출에 미치는 영향을 추적", fontsize=12, color=MUTED, transform=ax.transAxes)

    stages = [
        (0.10, "01", "업무 요청", "회의 일정 조율\n문서 검토·메일 요약", BLUE),
        (0.30, "02", "접근 조건", "전체 / 오라클 최소\nLLM 도구 선택", CYAN),
        (0.50, "03", "데이터 도구", "연락처 15 · 이메일 33\n캘린더 7", AMBER),
        (0.70, "04", "접근 로그", "읽은 ID · 필수 ID\n악성 페이로드 노출", RED),
        (0.90, "05", "평가", "접근 정밀도 · 포괄률\n초과 민감도", GREEN),
    ]
    width = 0.16
    for idx, (x, num, title, body, color) in enumerate(stages):
        rounded_box(ax, (x - width / 2, 0.48), width, 0.25, WHITE, edgecolor=GRID, radius=0.02)
        ax.text(x - width / 2 + 0.018, 0.68, num, color=color, fontsize=12, fontweight="bold", transform=ax.transAxes)
        ax.text(x - width / 2 + 0.018, 0.615, title, color=NAVY, fontsize=15, fontweight="bold", transform=ax.transAxes)
        ax.text(x - width / 2 + 0.018, 0.535, body, color=SLATE, fontsize=10, transform=ax.transAxes, linespacing=1.5)
        if idx < len(stages) - 1:
            ax.annotate("", xy=(x + 0.115, 0.605), xytext=(x + 0.085, 0.605), xycoords=ax.transAxes,
                        arrowprops=dict(arrowstyle="-|>", color="#94A3B8", lw=1.6))

    metric_cards = [
        (0.08, "접근 정밀도", "필수 접근 ÷ 전체 접근", BLUE),
        (0.31, "필수정보 포괄률", "접근한 필수 ID ÷ 전체 필수 ID", GREEN),
        (0.54, "초과 민감도", "업무 외 접근 항목의 민감도 합", RED),
        (0.77, "공격표면", "접근한 악성 페이로드 수", AMBER),
    ]
    for x, title, body, color in metric_cards:
        rounded_box(ax, (x, 0.15), 0.19, 0.16, "#EEF2FF", radius=0.015)
        ax.add_patch(patches.Circle((x + 0.025, 0.25), 0.009, transform=ax.transAxes, facecolor=color, edgecolor="none"))
        ax.text(x + 0.045, 0.245, title, fontsize=11.5, fontweight="bold", color=NAVY, transform=ax.transAxes)
        ax.text(x + 0.025, 0.19, body, fontsize=9.5, color=MUTED, transform=ax.transAxes)

    ax.text(0.05, 0.065, "현재 단계: 접근 로그 감사까지 완료 · 실제 도구 실행, 업무 산출물 판정, 공격 지시 준수 여부는 후속 실험 대상", fontsize=10, color=RED, transform=ax.transAxes, fontweight="bold")
    save(fig, "readme_method.png")


def results_dashboard():
    fig = plt.figure(figsize=(16, 9), facecolor=WHITE)
    gs = fig.add_gridspec(2, 2, height_ratios=[0.22, 0.78], width_ratios=[1.15, 0.85], hspace=0.08, wspace=0.25)
    title_ax = fig.add_subplot(gs[0, :])
    title_ax.axis("off")
    title_ax.text(0.0, 0.67, "S1 핵심 결과", fontsize=26, fontweight="bold", color=NAVY)
    title_ax.text(0.0, 0.28, "필요한 정보를 빠뜨리지 않으면서 초과 접근을 얼마나 줄였는가", fontsize=12, color=MUTED)

    bar_ax = fig.add_subplot(gs[1, 0])
    scatter_ax = fig.add_subplot(gs[1, 1])

    labels = ["전체 접근 A", "최소정보 B", "Qwen3 C"]
    values = [result for _, result in condition_values()]
    required = np.array([result["required_accessed"] for result in values])
    excess = np.array([result["excess_items"] for result in values])
    missing = np.array([result["missing_required"] for result in values])
    y = np.arange(len(labels))
    bar_ax.barh(y, required, color=BLUE, label="필수 접근")
    bar_ax.barh(y, excess, left=required, color=RED, label="초과 접근")
    for i, (req, exc, miss) in enumerate(zip(required, excess, missing)):
        bar_ax.text(req / 2, i, str(req), color=WHITE, ha="center", va="center", fontweight="bold")
        if exc:
            bar_ax.text(req + exc / 2, i, str(exc), color=WHITE, ha="center", va="center", fontweight="bold")
        if miss:
            bar_ax.text(req + exc + 1.0, i, f"필수 {miss}개 누락", color=AMBER, va="center", fontweight="bold")
    bar_ax.set_yticks(y)
    bar_ax.set_yticklabels(labels)
    bar_ax.invert_yaxis()
    bar_ax.set_xlabel("접근 데이터 항목 수")
    bar_ax.set_title("접근범위 분해", loc="left", fontsize=15, fontweight="bold", color=NAVY)
    bar_ax.legend(frameon=False, loc="lower right")
    bar_ax.grid(axis="x", linestyle="--", alpha=0.25)
    bar_ax.spines[["top", "right", "left"]].set_visible(False)

    colors = [RED, GREEN, AMBER]
    markers = ["o", "s", "^"]
    for label, result, color, marker in zip(labels, values, colors, markers):
        x = result["excess_sensitive_exposure"]
        yv = result["required_coverage"] * 100
        scatter_ax.scatter(x, yv, s=180, color=color, marker=marker, edgecolor=WHITE, linewidth=1.5, zorder=4)
        scatter_ax.annotate(label, (x, yv), xytext=(8, 8), textcoords="offset points", fontsize=10, fontweight="bold")
    max_x = max(result["excess_sensitive_exposure"] for result in values)
    scatter_ax.add_patch(patches.Rectangle((0, 90), max_x * 0.15, 10, facecolor="#D1FAE5", edgecolor="none", alpha=0.85))
    scatter_ax.text(max_x * 0.075, 95, "이상적", color=GREEN, ha="center", va="center", fontweight="bold")
    scatter_ax.set_xlim(-0.5, max_x * 1.15)
    scatter_ax.set_ylim(0, 108)
    scatter_ax.set_xlabel("초과 민감도 (낮을수록 좋음)")
    scatter_ax.set_ylabel("필수정보 포괄률 (%)")
    scatter_ax.set_title("프라이버시–업무충족도", loc="left", fontsize=15, fontweight="bold", color=NAVY)
    scatter_ax.grid(linestyle="--", alpha=0.25)
    scatter_ax.spines[["top", "right"]].set_visible(False)

    fig.text(0.02, 0.025, "B는 필수 ID를 미리 아는 오라클이며, C의 포괄률은 실제 성공률이 아니라 필수 ID 접근 비율이다.", fontsize=9.5, color=MUTED)
    save(fig, "readme_results.png")


def attack_surface():
    fig, ax = plt.subplots(figsize=(16, 6.6))
    fig.patch.set_facecolor(NAVY)
    ax.set_facecolor(NAVY)
    ax.axis("off")
    ax.text(0.05, 0.88, "프롬프트 인젝션 공격표면", fontsize=26, fontweight="bold", color=WHITE, transform=ax.transAxes)
    ax.text(0.05, 0.81, "악성 이메일을 읽을 기회가 있었는지와 실제 공격 성공은 구분해야 한다", fontsize=12, color="#CBD5E1", transform=ax.transAxes)

    entries = [
        (0.08, "전체 접근 A", 5, "악성 이메일 5건 접근", RED, "공격표면 열림"),
        (0.38, "최소정보 B", 0, "악성 이메일 미접근", GREEN, "공격표면 축소"),
        (0.68, "Qwen3 C", 0, "S1에서 이메일 도구 미선택", CYAN, "공격표면 축소"),
    ]
    for x, title, count, description, color, status in entries:
        rounded_box(ax, (x, 0.24), 0.24, 0.43, "#172554", edgecolor="#334155", radius=0.025)
        ax.text(x + 0.025, 0.61, title, fontsize=15, color=WHITE, fontweight="bold", transform=ax.transAxes)
        ax.text(x + 0.025, 0.47, str(count), fontsize=42, color=color, fontweight="bold", transform=ax.transAxes)
        ax.text(x + 0.082, 0.49, "개 페이로드", fontsize=11, color="#CBD5E1", transform=ax.transAxes)
        ax.text(x + 0.025, 0.39, description, fontsize=10.5, color="#E2E8F0", transform=ax.transAxes)
        ax.text(x + 0.025, 0.31, status, fontsize=11, color=color, fontweight="bold", transform=ax.transAxes)

    rounded_box(ax, (0.05, 0.08), 0.90, 0.075, "#3F1D2B", edgecolor="#7F1D1D", radius=0.015)
    ax.text(0.075, 0.105, "해석 한계", fontsize=10.5, color="#FCA5A5", fontweight="bold", transform=ax.transAxes)
    ax.text(0.16, 0.105, "현재 구현은 이메일 접근 여부만 기록한다. 공격 명령 실행·외부 전송·실제 개인정보 유출은 아직 측정하지 않았다.", fontsize=10.5, color=WHITE, transform=ax.transAxes)
    save(fig, "readme_attack_surface.png")


def scenario_overview():
    rows = summary["scenario_scope"]
    fig, ax = plt.subplots(figsize=(16, 7.4))
    fig.patch.set_facecolor(WHITE)
    ax.axis("off")
    ax.text(0.05, 0.91, "4개 업무 시나리오의 접근범위", fontsize=25, fontweight="bold", color=NAVY, transform=ax.transAxes)
    ax.text(0.05, 0.855, "전체 제공 55개와 사전 정의 최소 집합 4~5개의 구조적 차이", fontsize=12, color=MUTED, transform=ax.transAxes)

    xs = [0.06, 0.29, 0.52, 0.75]
    icon_labels = ["S1", "S2", "S3", "S4"]
    for x, sid, row in zip(xs, icon_labels, rows):
        rounded_box(ax, (x, 0.24), 0.19, 0.49, PAPER, edgecolor=GRID, radius=0.022)
        ax.text(x + 0.025, 0.66, sid, fontsize=12, color=BLUE, fontweight="bold", transform=ax.transAxes)
        ax.text(x + 0.025, 0.60, row["title"], fontsize=15, color=NAVY, fontweight="bold", transform=ax.transAxes)
        a = row["A"]["accessed"]
        b = row["B"]["accessed"]
        reduction = (1 - b / a) * 100
        ax.text(x + 0.025, 0.47, str(a), fontsize=34, color=RED, fontweight="bold", transform=ax.transAxes)
        ax.text(x + 0.09, 0.49, "전체", fontsize=10, color=MUTED, transform=ax.transAxes)
        ax.annotate("", xy=(x + 0.15, 0.47), xytext=(x + 0.115, 0.47), xycoords=ax.transAxes,
                    arrowprops=dict(arrowstyle="-|>", color="#94A3B8", lw=1.5))
        ax.text(x + 0.025, 0.36, str(b), fontsize=30, color=GREEN, fontweight="bold", transform=ax.transAxes)
        ax.text(x + 0.075, 0.38, "최소", fontsize=10, color=MUTED, transform=ax.transAxes)
        ax.text(x + 0.025, 0.285, f"접근범위 −{reduction:.1f}%", fontsize=11.5, color=GREEN, fontweight="bold", transform=ax.transAxes)

    ax.text(0.05, 0.12, "주의", fontsize=11, color=AMBER, fontweight="bold", transform=ax.transAxes)
    ax.text(0.105, 0.12, "최소 집합은 알고리즘이 찾아낸 값이 아니라 scenarios.json에 사람이 지정한 정답 집합이다.", fontsize=10.5, color=SLATE, transform=ax.transAxes)
    save(fig, "readme_scenarios.png")


def main():
    print("Generating README visuals:")
    hero()
    method_diagram()
    results_dashboard()
    attack_surface()
    scenario_overview()


if __name__ == "__main__":
    main()
