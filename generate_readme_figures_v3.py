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
    ax.text(0.045, 0.685, "위험은 모델 성향이 아니라 인터페이스 설계에 있다 — 도구 권한이 노출 '용량'을 결정한다",
            color=GRAY, fontsize=11.5)

    cards = [
        (RED, "무방어 인터페이스 (A)", "151.5", "민감필드 노출 용량 (worst-case)", "악성 인젝션 전달 5건"),
        (GREEN, "필드 최소권한 (C)", "10.5", "민감필드 노출 용량  (93%↓)", "악성 인젝션 전달 0건"),
        (AMBER, "실제 모델 행동", "0.4", "평균 접근 (좁은 업무)", "과소접근 — 광범위도 1.1"),
    ]
    x0, w, gap, y, h = 0.045, 0.29, 0.022, 0.16, 0.40
    for i, (acc, title, big, lab, sub) in enumerate(cards):
        x = x0 + i * (w + gap)
        card(ax, x, y, w, h, acc)
        ax.text(x + 0.018, y + h - 0.06, title, color=acc, fontsize=11.5, fontweight="bold")
        ax.text(x + 0.018, y + h - 0.205, big, color=WHITE, fontsize=30, fontweight="bold")
        ax.text(x + 0.018, y + 0.085, lab, color=GRAY, fontsize=10)
        ax.text(x + 0.018, y + 0.035, sub, color=WHITE, fontsize=10, fontweight="bold")

    ax.text(0.045, 0.045, "4모델(검증통과) × 48시나리오 × 4조건 = 768 runs   ·   qwen2.5:3b/7b · qwen3:8b · llama3.1:8b",
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
    ax.text(0.04, 0.815, "도구 인터페이스 권한 설계가 개인정보 노출 용량과 프롬프트 인젝션 위험에 미치는 영향 측정",
            color="#5A6B7B", fontsize=11)

    steps = [
        ("01", "업무 요청", "48 시나리오\n(40좁은+8광범위)"),
        ("02", "실제 에이전트 루프", "plan → tool call →\nobserve → 최종답변"),
        ("03", "세분화 도구", "연락처15·이메일33\n·캘린더7 (악성5)"),
        ("04", "정책 미들웨어", "A 무방어 / B 프롬프트\nC 필드최소권한 / D 강함"),
        ("05", "측정", "노출용량·접근범위\n인젝션 차단·성공률"),
    ]
    x0, w, gap, y, h = 0.04, 0.172, 0.018, 0.42, 0.27
    for i, (n, t, b) in enumerate(steps):
        x = x0 + i * (w + gap)
        step(ax, x, y, w, h, n, t, b)
        if i < len(steps) - 1:
            ax.annotate("", xy=(x + w + gap, y + h / 2), xytext=(x + w, y + h / 2),
                        arrowprops=dict(arrowstyle="-|>", color="#9FB3C8", lw=1.6))

    chips = [
        (BLUE, "노출 용량 (설계 상한)"),
        (GREEN, "민감필드 접근 (실제 행동)"),
        (RED, "인젝션 전달 차단"),
        (AMBER, "업무 성공률"),
    ]
    cx, cy, cw = 0.06, 0.20, 0.225
    for i, (col, lab) in enumerate(chips):
        x = cx + i * cw
        ax.add_patch(plt.Circle((x, cy + 0.012), 0.008, color=col, transform=ax.transData))
        ax.text(x + 0.018, cy, lab, color="#1B2A3A", fontsize=9.5, fontweight="bold", va="center")

    ax.text(0.04, 0.075, "현재: 768 runs(4모델·48시나리오) · 노출 용량 93%↓ · "
            "광범위 업무 실현노출 5.3→0.0 · 인젝션 5→0건 구조 차단",
            color=RED, fontsize=9.5, fontweight="bold")
    out = os.path.join(FIG_DIR, "readme_method.png")
    fig.savefig(out, facecolor="#F4F7FB"); plt.close(fig)
    return out


if __name__ == "__main__":
    os.makedirs(FIG_DIR, exist_ok=True)
    print("Wrote:", hero())
    print("Wrote:", method())
