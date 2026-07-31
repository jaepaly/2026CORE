#!/usr/bin/env python3
"""Figures for the v3 study, drawn from committed run artifacts.

    python figures_v3.py --experiment-dir experiments/main-qwen2.5-3b [--experiment-dir ...]

Every figure is generated from `runs.jsonl`, never hand-edited, so a number on a
poster can always be traced back to the runs that produced it.

The layer separation the protocol requires is carried into the plots: delivered
exposure and task outcome are drawn as separate panels rather than combined into
a single "safety score", and the primary A-vs-C endpoint is labelled as such so
a reader cannot mistake a secondary contrast for the pre-registered one.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt

from analysis_experiment_v3 import CONDITIONS, analyse

for _candidate in ["Malgun Gothic", "AppleGothic", "NanumGothic", "Gulim"]:
    if any(_candidate == font.name for font in fm.fontManager.ttflist):
        plt.rcParams["font.family"] = _candidate
        break
plt.rcParams["axes.unicode_minus"] = False
# Malgun Gothic lacks U+2212; use the ASCII hyphen in labels we author too.
MINUS = "-"

ROOT = Path(__file__).resolve().parent
#: A/B share a colour and C/D share another: the factor that matters here is
#: whether field projection is on, not the prompt wording.
COLOURS = {"A": "#E45756", "B": "#F58518", "C": "#4C78A8", "D": "#54A24B"}


def _bar(ax, values: dict, title: str, ylabel: str, fmt: str = "{:.2f}") -> None:
    conditions = [c for c in CONDITIONS if values.get(c) is not None]
    heights = [values[c] for c in conditions]
    bars = ax.bar(conditions, heights, color=[COLOURS[c] for c in conditions])
    for bar, height in zip(bars, heights):
        ax.text(bar.get_x() + bar.get_width() / 2, height, fmt.format(height),
                ha="center", va="bottom", fontsize=9)
    ax.set_title(title, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_ylim(0, max(heights + [0.01]) * 1.25)


def figure_layers(summary: dict, out_dir: Path) -> Path:
    """Delivery and behaviour side by side — never merged into one score."""
    delivery = summary["delivery"]
    behaviour = summary["behaviour"]
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))

    _bar(axes[0],
         {c: delivery[c]["mean_delivered_sensitive_fields"] for c in delivery},
         "전달 계층: 실제 전달된 민감 필드", "run당 평균 민감 필드")
    _bar(axes[1],
         {c: behaviour[c]["task_success_rate"] for c in behaviour},
         "행동 계층: 업무 성공률", "유효 run 중 비율")
    _bar(axes[2],
         {c: behaviour[c]["safe_completion_rate"] for c in behaviour},
         "엔드포인트: safe_completion", "유효 run 중 비율")

    fig.suptitle("조건별 3계층 — 전달·행동·엔드포인트를 하나로 합치지 않는다", fontsize=12)
    fig.tight_layout()
    out = out_dir / "fig_v3_layers.png"
    fig.savefig(out, dpi=180)
    plt.close(fig)
    return out


def figure_primary(summary: dict, out_dir: Path) -> Path:
    """The pre-registered A-vs-C contrast, with its discordant pairs shown."""
    primary = summary["primary"]
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 4))

    a_only = primary["a_only_success_count"]
    c_only = primary["c_only_success_count"]
    both = primary["paired_valid_unit_count"] - a_only - c_only
    labels = ["A만 safe", "C만 safe", "일치"]
    axes[0].bar(labels, [a_only, c_only, both], color=[COLOURS["A"], COLOURS["C"], "#B0B0B0"])
    for index, value in enumerate([a_only, c_only, both]):
        axes[0].text(index, value, str(value), ha="center", va="bottom", fontsize=9)
    axes[0].set_title(f"primary A vs C — McNemar p = {primary['mcnemar_exact_two_sided_p']:.4f}",
                      fontsize=11)
    axes[0].set_ylabel("(model, scenario) 단위 수", fontsize=9)

    bootstrap = primary.get("delivered_sensitive_fields_a_minus_c")
    if bootstrap:
        low, high = bootstrap["bootstrap_95_ci"]
        mean = bootstrap["mean_difference_a_minus_c"]
        axes[1].errorbar([mean], [0], xerr=[[mean - low], [high - mean]], fmt="o",
                         color=COLOURS["A"], capsize=6, markersize=9)
        axes[1].axvline(0, color="#888", linestyle="--", linewidth=1)
        axes[1].set_yticks([])
        axes[1].set_xlabel(f"A {MINUS} C (run당 민감 필드 차이)", fontsize=9)
        axes[1].set_title(f"민감 전달 차이 {mean:.2f}  (95% CI {low:.2f}~{high:.2f})", fontsize=11)
    else:
        axes[1].axis("off")
        axes[1].text(0.5, 0.5, "짝지어진 유효 run 부족", ha="center", va="center")

    fig.suptitle("사전 등록한 주 비교 — 나머지 대조는 secondary", fontsize=12)
    fig.tight_layout()
    out = out_dir / "fig_v3_primary.png"
    fig.savefig(out, dpi=180)
    plt.close(fig)
    return out


def figure_by_model(summary: dict, out_dir: Path) -> Path | None:
    """Is the effect model-dependent, or does the interface decide it?"""
    by_model = summary["by_model"]
    if len(by_model) < 2:
        return None

    models = sorted(by_model)
    width = 0.2
    offsets = [-1.5 * width, -0.5 * width, 0.5 * width, 1.5 * width]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))

    for metric, ax, title in (
        ("mean_delivered_sensitive_fields", axes[0], "모델별 민감 전달"),
        ("safe_completion_rate", axes[1], "모델별 safe_completion"),
    ):
        for offset, condition in zip(offsets, CONDITIONS):
            values = [by_model[m].get(condition, {}).get(metric, 0) or 0 for m in models]
            ax.bar([i + offset for i in range(len(models))], values, width,
                   label=condition, color=COLOURS[condition])
        ax.set_xticks(range(len(models)))
        ax.set_xticklabels(models, rotation=12, fontsize=8)
        ax.set_title(title, fontsize=11)
        ax.legend(ncol=4, fontsize=8)

    fig.suptitle("효과가 모델에 좌우되는가, 인터페이스가 결정하는가", fontsize=12)
    fig.tight_layout()
    out = out_dir / "fig_v3_by_model.png"
    fig.savefig(out, dpi=180)
    plt.close(fig)
    return out


def figure_run_health(summary: dict, out_dir: Path) -> Path:
    """Dropout must be visible: a condition that fails more often is a finding."""
    behaviour = summary["behaviour"]
    conditions = [c for c in CONDITIONS if c in behaviour]
    valid = [behaviour[c]["valid_runs"] for c in conditions]
    max_turns = [behaviour[c]["max_turns_reached"] for c in conditions]
    technical = [behaviour[c]["technical_failures"] for c in conditions]

    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.bar(conditions, valid, label="유효", color="#54A24B")
    ax.bar(conditions, max_turns, bottom=valid, label="턴 소진(실패로 집계)", color="#F58518")
    ax.bar(conditions, technical, bottom=[v + m for v, m in zip(valid, max_turns)],
           label="기술 실패(분모 제외)", color="#E45756")
    ax.set_ylabel("run 수", fontsize=9)
    ax.set_title("조건별 실행 상태 — 탈락이 조건에 치우치면 비교가 편향된다", fontsize=11)
    ax.legend(fontsize=8)
    fig.tight_layout()
    out = out_dir / "fig_v3_run_health.png"
    fig.savefig(out, dpi=180)
    plt.close(fig)
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="v3 figures")
    parser.add_argument("--experiment-dir", action="append", required=True)
    parser.add_argument("--review-csv", default=str(ROOT / "data" / "scenario_review_v3.csv"))
    parser.add_argument("--out-dir", default=str(ROOT / "docs" / "figures"))
    args = parser.parse_args(argv)

    summary = analyse([Path(d) for d in args.experiment_dir], Path(args.review_csv))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    made = [figure_layers(summary, out_dir), figure_primary(summary, out_dir),
            figure_run_health(summary, out_dir)]
    by_model = figure_by_model(summary, out_dir)
    if by_model:
        made.append(by_model)
    else:
        print("모델이 1개뿐이라 모델별 비교 그림은 건너뜀")

    print(f"runs={summary['total_runs']}  models={', '.join(summary['models'])}")
    for path in made:
        print(f"  saved {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
