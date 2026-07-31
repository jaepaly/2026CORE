#!/usr/bin/env python3
"""README 상단 hero/method 배너를 interface-risk thesis + 실제 수치로 재생성.

기존 readme_hero.png / readme_method.png(옛 v1 수치: 55/22/oracle)를 덮어써
README 본문(2400런, 평균접근 0.65, 4조건)과 일치시킨다.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch

for _c in ["Malgun Gothic", "AppleGothic", "NanumGothic", "Gulim"]:
    if any(_c == f.name for f in fm.fontManager.ttflist):
        plt.rcParams["font.family"] = _c
        break
plt.rcParams["axes.unicode_minus"] = False

FIG_DIR = os.path.join(os.path.dirname(__file__), "docs", "figures")

BG = "#0E1726"
CARD = "#1B2A3A"
WHITE = "#F2F5F8"
GRAY = "#9FB3C8"
RED = "#E4574F"
GREEN = "#4FB477"
BLUE = "#4C8DE8"
AMBER = "#F2A93B"


def card(ax, x, y, w, h, accent):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
                                linewidth=2.2, edgecolor=accent, facecolor=CARD,
                                mutation_aspect=0.5))


def hero():
    fig = plt.figure(figsize=(11, 4.6), dpi=110)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, color=BG))
    ax.text(0.045, 0.90, "PRIVACY × AGENTIC AI", color=BLUE, fontsize=11, fontweight="bold")
    ax.text(0.045, 0.79, "AI 에이전트는 일을 위해 얼마나 많은 개인정보를 읽는가?",
            color=WHITE, fontsize=20, fontweight="bold")
    ax.text(0.045, 0.685, "\"적게 읽어라\"는 지시는 전달을 못 줄였다 — 인터페이스가 반환하지 않는 것만 전달되지 않았다",
            color=GRAY, fontsize=11.5)

    cards = [
        (RED, "projection 없음 (A·B)", "0.50", "run당 실제 전달된 민감 필드", "최소화 지시(B)도 0.52 — 못 줄임"),
        (GREEN, "task-aware projection (C·D)", "0.00", "run당 전달 민감 필드 (A-C CI 0.37~0.64)", "4모델 전 계열 동일"),
        (AMBER, "primary  A vs C", "p=0.07", "safe_completion — 유의하지 않음", "task 성공 3~6% → 검정력 부족"),
    ]
    x0, w, gap, y, h = 0.045, 0.29, 0.022, 0.16, 0.40
    for i, (acc, title, big, lab, sub) in enumerate(cards):
        x = x0 + i * (w + gap)
        card(ax, x, y, w, h, acc)
        ax.text(x + 0.018, y + h - 0.06, title, color=acc, fontsize=11.5, fontweight="bold")
        ax.text(x + 0.018, y + h - 0.205, big, color=WHITE, fontsize=30, fontweight="bold")
        ax.text(x + 0.018, y + 0.085, lab, color=GRAY, fontsize=10)
        ax.text(x + 0.018, y + 0.035, sub, color=WHITE, fontsize=10, fontweight="bold")

    ax.text(0.045, 0.045, "사전 등록 2×2 · 4모델 × 43시나리오 × 4조건 = 688 runs · 기술 실패 0   ·   qwen2.5:3b/7b · qwen3:8b · llama3.1:8b",
            color=GRAY, fontsize=9.5)
    out = os.path.join(FIG_DIR, "readme_hero.png")
    fig.savefig(out, facecolor=BG); plt.close(fig)
    return out


def step(ax, x, y, w, h, num, title, body):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.01,rounding_size=0.02",
                                linewidth=1.6, edgecolor="#D8E0EA", facecolor="white"))
    ax.text(x + 0.014, y + h - 0.05, num, color=BLUE, fontsize=12, fontweight="bold")
    ax.text(x + 0.014, y + h - 0.12, title, color="#1B2A3A", fontsize=10.5, fontweight="bold")
    ax.text(x + 0.014, y + 0.05, body, color="#5A6B7B", fontsize=8.6, va="bottom")


def method():
    fig = plt.figure(figsize=(11, 4.6), dpi=110)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, color="#F4F7FB"))
    ax.text(0.04, 0.90, "연구 설계", color="#13233A", fontsize=19, fontweight="bold")
    ax.text(0.04, 0.815, "사전 등록 2×2: 프롬프트 축(중립 vs 최소화 지시) × projection 축(없음 vs task-aware 필드 projection)",
            color="#5A6B7B", fontsize=11)

    steps = [
        ("01", "시나리오 라벨", "2인 독립 검토+게이트\n승인 43 / 폐기 5"),
        ("02", "모델 파일럿", "tool-call ≥80%만 채택\nmistral·14b 제외"),
        ("03", "사전 등록 2×2", "A중립 B지시\nC projection D둘다"),
        ("04", "본 실험", "4모델×43×4 = 688 runs\nmanifest 해시 동결"),
        ("05", "3계층 보고", "전달 / 행동 /\n엔드포인트 분리"),
    ]
    x0, w, gap, y, h = 0.04, 0.172, 0.018, 0.42, 0.27
    for i, (n, t, b) in enumerate(steps):
        x = x0 + i * (w + gap)
        step(ax, x, y, w, h, n, t, b)
        if i < len(steps) - 1:
            ax.annotate("", xy=(x + w + gap, y + h / 2), xytext=(x + w, y + h / 2),
                        arrowprops=dict(arrowstyle="-|>", color="#9FB3C8", lw=1.6))

    chips = [
        (BLUE, "전달: run당 민감 필드"),
        (GREEN, "행동: task 성공률"),
        (RED, "엔드포인트: safe_completion"),
        (AMBER, "primary = A vs C만"),
    ]
    cx, cy, cw = 0.06, 0.20, 0.225
    for i, (col, lab) in enumerate(chips):
        x = cx + i * cw
        ax.add_patch(plt.Circle((x, cy + 0.012), 0.008, color=col, transform=ax.transData))
        ax.text(x + 0.018, cy, lab, color="#1B2A3A", fontsize=9.5, fontweight="bold", va="center")

    ax.text(0.04, 0.075, "결과: 전달 A 0.50 → C 0.00 (95% CI 0.37~0.64, 4모델 동일) · "
            "프롬프트 지시 효과 없음(B 0.52) · primary p=0.070 유의하지 않음(정직 보고)",
            color=RED, fontsize=9.5, fontweight="bold")
    out = os.path.join(FIG_DIR, "readme_method.png")
    fig.savefig(out, facecolor="#F4F7FB"); plt.close(fig)
    return out


if __name__ == "__main__":
    os.makedirs(FIG_DIR, exist_ok=True)
    print("Wrote:", hero())
    print("Wrote:", method())
