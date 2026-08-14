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
    """Per model: how many fields granted vs the reviewer, split by direction.

    The domain-level score is drawn as a hatched overlay inside each bar, so the
    gap between the two is readable as a quantity: it is the part of the error
    that comes from naming the wrong tool of a domain rather than from picking
    the wrong field.  Plotting only the tool-level bar would present a
    tool-vocabulary slip as a privacy misjudgement.
    """
    models = list(summary["by_model"])
    tool = summary["by_model"]
    domain = summary["domain_level"]["by_model"]
    over = [tool[m]["mean_over_permission"] for m in models]
    under = [tool[m]["mean_over_restriction"] for m in models]
    over_domain = [domain.get(m, {}).get("mean_over_permission", 0) for m in models]
    under_domain = [domain.get(m, {}).get("mean_over_restriction", 0) for m in models]
    sensitive = [tool[m]["mean_sensitive_over_permission"] for m in models]

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6))
    positions = list(range(len(models)))
    width = 0.34

    left = [p - width / 2 for p in positions]
    right = [p + width / 2 for p in positions]
    axes[0].bar(left, over, width, label="과잉 허용", color=OVER_PERMISSION)
    axes[0].bar(right, under, width, label="과잉 차단", color=OVER_RESTRICTION)
    axes[0].bar(left, over_domain, width, color="none", edgecolor="white",
                hatch="///", linewidth=0)
    axes[0].bar(right, under_domain, width, color="none", edgecolor="white",
                hatch="///", linewidth=0, label="빗금: 도메인 단위 (도구 혼동 제외)")
    axes[0].set_xticks(positions)
    axes[0].set_xticklabels(models, rotation=12, fontsize=8)
    axes[0].set_xlim(-0.6, len(models) - 0.4)
    axes[0].set_ylabel("시나리오당 필드 수", fontsize=9)
    axes[0].set_title("두 오류는 결과가 반대다 — 합치지 않는다", fontsize=11)
    axes[0].legend(fontsize=8)

    axes[1].bar(positions, sensitive, width * 1.5, color=OVER_PERMISSION)
    for index, value in enumerate(sensitive):
        axes[1].text(index, value, f"{value:.2f}", ha="center", va="bottom", fontsize=9)
    axes[1].set_xticks(positions)
    axes[1].set_xticklabels(models, rotation=12, fontsize=8)
    axes[1].set_xlim(-0.6, len(models) - 0.4)
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
    ax.text(len(models) - 0.45, reviewer, f"인간 검토자 {reviewer:.1f} ",
            va="bottom", ha="right", fontsize=9, color=REVIEWER)
    ax.set_xlim(-0.6, len(models) - 0.4)
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


def figure_omitted_fields(summary: dict, out_dir: Path, top: int = 10) -> Path | None:
    """Which required fields the models withhold, as a share of times required.

    The bars are uniformly high -- the models omit most of what the reviewers
    required, not one unlucky field.  The identifier fields are coloured apart
    not because they are omitted more (``contact.role`` is omitted more) but
    because omitting them costs something different in kind: without ``id`` a
    search hit cannot become a detail lookup, so the policy does not merely lose
    a display field, it severs the retrieval chain.  Claiming identifiers are
    *the* omission would misread this chart; they are the consequential subset
    of a broad omission.
    """
    errors = summary["field_errors"]
    occurrences = errors["reviewer_allowed_occurrences"]
    rates = [
        (field, count / occurrences[field], count, occurrences[field])
        for field, count in errors["over_restriction"].items()
        if occurrences.get(field, 0) >= 8
    ]
    if not rates:
        return None
    rates.sort(key=lambda row: -row[1])
    rates = rates[:top]

    labels = [row[0] for row in rates][::-1]
    values = [row[1] for row in rates][::-1]
    colours = ["#B4651B" if label.endswith(".id") else OVER_RESTRICTION for label in labels]

    fig, ax = plt.subplots(figsize=(9, 3.4 + 0.32 * len(labels)))
    ax.barh(labels, values, color=colours)
    for index, (_, rate, count, total) in enumerate(rates[::-1]):
        ax.text(rate, index, f"  {count}/{total}", va="center", fontsize=8)
    ax.set_xlim(0, 1.08)
    ax.set_xlabel("검토자가 필요하다고 한 시나리오 중 모델이 뺀 비율", fontsize=9)
    ax.set_title("모델은 필요한 필드 대부분을 빠뜨린다 — 주황은 식별자", fontsize=11)
    ax.text(1.0, -0.9, "식별자 누락은 표시 필드 하나를 잃는 것이 아니라 검색 연결이 끊기는 것",
            fontsize=8, color="#B4651B", ha="right")
    fig.tight_layout()
    out = out_dir / "fig_policy_omitted_fields.png"
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
    for optional in (figure_sensitive_grants(summary, out_dir),
                     figure_omitted_fields(summary, out_dir)):
        if optional:
            made.append(optional)

    print(f"calls={summary['total_calls']}  models={', '.join(summary['models'])}")
    for path in made:
        print(f"  saved {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
