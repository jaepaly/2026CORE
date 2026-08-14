#!/usr/bin/env python3
"""Figures for the policy-authoring experiment.

    python figures_policy_authoring_v3.py --experiment-dir experiments/policy-authoring

Drawn from ``policies.jsonl`` so every number on the poster traces back to a
recorded call.  The error directions are drawn apart rather than stacked into an
accuracy bar: the whole argument is that granting too much and withholding too
much are different failures with different remedies, and a single bar would hide
exactly that.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt

from analysis_policy_authoring_v3 import analyse

for _candidate in ["Malgun Gothic", "AppleGothic", "NanumGothic", "Gulim"]:
    if any(_candidate == font.name for font in fm.fontManager.ttflist):
        plt.rcParams["font.family"] = _candidate
        break
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent
OVER_PERMISSION = "#E45756"   # leaks
OVER_RESTRICTION = "#4C78A8"  # blocks work
REVIEWER = "#7F7F7F"


def figure_error_directions(summary: dict, out_dir: Path) -> Path:
    """Per model: how many fields granted vs the reviewer, split by direction."""
    models = list(summary["by_model"])
    over = [summary["by_model"][m]["mean_over_permission"] for m in models]
    sensitive = [summary["by_model"][m]["mean_sensitive_over_permission"] for m in models]
    under = [summary["by_model"][m]["mean_over_restriction"] for m in models]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    positions = range(len(models))
    width = 0.36

    axes[0].bar([p - width / 2 for p in positions], over, width,
                label="과잉 허용 (검토자가 뺀 필드를 줌)", color=OVER_PERMISSION)
    axes[0].bar([p + width / 2 for p in positions], under, width,
                label="과잉 차단 (검토자가 준 필드를 뺌)", color=OVER_RESTRICTION)
    axes[0].set_xticks(list(positions))
    axes[0].set_xticklabels(models, rotation=12, fontsize=8)
    axes[0].set_ylabel("시나리오당 필드 수", fontsize=9)
    axes[0].set_title("두 오류는 결과가 반대다 — 합치지 않는다", fontsize=11)
    axes[0].legend(fontsize=8)

    axes[1].bar(list(positions), sensitive, width * 1.6, color=OVER_PERMISSION)
    for index, value in enumerate(sensitive):
        axes[1].text(index, value, f"{value:.2f}", ha="center", va="bottom", fontsize=9)
    axes[1].set_xticks(list(positions))
    axes[1].set_xticklabels(models, rotation=12, fontsize=8)
    axes[1].set_ylabel("시나리오당 민감 필드 수", fontsize=9)
    axes[1].set_title("검토자가 금지한 민감 필드를 허용한 양", fontsize=11)
    axes[1].set_ylim(0, max(sensitive + [0.05]) * 1.3)

    fig.suptitle("모델이 최소권한 정책을 쓰면 어느 쪽으로 틀리는가", fontsize=12)
    fig.tight_layout()
    out = out_dir / "fig_policy_error_directions.png"
    fig.savefig(out, dpi=180)
    plt.close(fig)
    return out


def figure_policy_size(summary: dict, out_dir: Path) -> Path:
    """Policy breadth against the human standard."""
    models = list(summary["by_model"])
    model_fields = [summary["by_model"][m]["mean_model_fields"] for m in models]
    reviewer = summary["overall"]["mean_reviewer_fields"]

    fig, ax = plt.subplots(figsize=(7.8, 4.2))
    bars = ax.bar(models, model_fields, color="#54A24B")
    for bar, value in zip(bars, model_fields):
        ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.1f}",
                ha="center", va="bottom", fontsize=9)
    ax.axhline(reviewer, color=REVIEWER, linestyle="--", linewidth=1.4)
    ax.text(len(models) - 0.5, reviewer, f" 인간 검토자 {reviewer:.1f}",
            va="bottom", ha="right", fontsize=9, color=REVIEWER)
    ax.set_ylabel("시나리오당 허용 필드 수", fontsize=9)
    ax.set_title("모델이 쓴 정책의 폭 vs 사람이 쓴 정책의 폭", fontsize=11)
    ax.tick_params(axis="x", rotation=12, labelsize=8)
    fig.tight_layout()
    out = out_dir / "fig_policy_size.png"
    fig.savefig(out, dpi=180)
    plt.close(fig)
    return out


def figure_sensitive_grants(summary: dict, out_dir: Path) -> Path | None:
    """Which forbidden fields get granted, and how often.

    A concentrated profile means a review queue can be narrowed to those fields;
    a flat one means it cannot.
    """
    profile = summary["sensitive_fields"]
    if not profile:
        return None
    keys = list(profile)
    rates = [profile[k]["grant_rate"] for k in keys]

    fig, ax = plt.subplots(figsize=(8.6, 3.6 + 0.35 * len(keys)))
    ax.barh(keys[::-1], rates[::-1], color=OVER_PERMISSION)
    for index, key in enumerate(keys[::-1]):
        stats = profile[key]
        ax.text(stats["grant_rate"], index,
                f"  {stats['granted_by_model']}/{stats['forbidden_in_scenarios']}",
                va="center", fontsize=8)
    ax.set_xlabel("검토자가 금지한 시나리오 중 모델이 허용한 비율", fontsize=9)
    ax.set_xlim(0, max(rates + [0.05]) * 1.25)
    ax.set_title("어떤 민감 필드에서 판단이 갈리는가", fontsize=11)
    fig.tight_layout()
    out = out_dir / "fig_policy_sensitive_grants.png"
    fig.savefig(out, dpi=180)
    plt.close(fig)
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="policy-authoring figures")
    parser.add_argument("--experiment-dir", action="append", required=True)
    parser.add_argument("--out-dir", default=str(ROOT / "docs" / "figures"))
    args = parser.parse_args(argv)

    summary = analyse([Path(d) for d in args.experiment_dir])
    if not summary["total_calls"]:
        print("no policies found")
        return 2
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    made = [figure_error_directions(summary, out_dir), figure_policy_size(summary, out_dir)]
    grants = figure_sensitive_grants(summary, out_dir)
    if grants:
        made.append(grants)

    print(f"calls={summary['total_calls']}  models={', '.join(summary['models'])}")
    for path in made:
        print(f"  saved {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
