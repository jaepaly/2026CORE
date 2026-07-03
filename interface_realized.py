#!/usr/bin/env python3
"""Realized sensitive-exposure analysis.

`interface_risk.py` measures design capacity: what could be exposed if a model
read everything allowed by the interface.  This script measures realized
exposure: among the IDs actually accessed by the agent, how much sensitive
field content would be delivered after each policy's field filtering.

Important policy semantics:
- A: no field filter.
- B: prompt-only minimization.  No field filter, so realized sensitive fields
  are the same kind of fields as A when the model accesses an item.
- C/D: field-level minimization removes email body and contact phone/notes.
  Calendar event details are still returned in the current policy.
"""

from __future__ import annotations

import glob
import json
import os
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt

for _candidate in ["Malgun Gothic", "AppleGothic", "NanumGothic", "Gulim"]:
    if any(_candidate == f.name for f in fm.fontManager.ttflist):
        plt.rcParams["font.family"] = _candidate
        break
plt.rcParams["axes.unicode_minus"] = False


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
FIG_DIR = ROOT / "docs" / "figures"
SUMMARY = OUTPUT_DIR / "realized_exposure_summary.json"
SENSITIVITY_SUMMARY = OUTPUT_DIR / "realized_exposure_sensitivity.json"


DEFAULT_WEIGHTS = {
    "contact_phone_notes": 5.0,  # phone(2) + notes(3)
    "email_body": 2.0,
    "calendar_events": 1.5,
}

WEIGHT_SCHEMES = {
    "default": DEFAULT_WEIGHTS,
    "equal": {"contact_phone_notes": 1.0, "email_body": 1.0, "calendar_events": 1.0},
    "conservative": {"contact_phone_notes": 2.0, "email_body": 1.0, "calendar_events": 1.0},
    "aggressive": {"contact_phone_notes": 8.0, "email_body": 5.0, "calendar_events": 2.0},
    "pii_heavy": {"contact_phone_notes": 7.0, "email_body": 2.0, "calendar_events": 1.0},
}


def realized_sensitive(iid: str, condition: str, weights: dict[str, float] | None = None) -> float:
    """Return realized sensitive-field score for one accessed ID.

    B is intentionally grouped with A because B is prompt-only minimization and
    does not remove fields from tool results.
    """

    weights = weights or DEFAULT_WEIGHTS
    condition = (condition or "").upper()

    if iid.startswith("cal"):
        return float(weights["calendar_events"])

    if condition in {"A", "B"}:
        if iid.startswith("c"):
            return float(weights["contact_phone_notes"])
        if iid.startswith("e"):
            return float(weights["email_body"])

    # C/D remove contact phone/notes and email body in the current policy.
    return 0.0


def load_rows_and_broad_set() -> tuple[list[dict], set[str], str]:
    scenarios = json.loads((DATA_DIR / "scenarios_v2.json").read_text(encoding="utf-8"))["scenarios"]
    broad = {s["id"] for s in scenarios if s.get("broad")}

    rows: list[dict] = []
    for p in glob.glob(str(OUTPUT_DIR / "runs_*.jsonl")):
        base = os.path.basename(p)
        if base == "runs.jsonl" or base.startswith("runs_v3_"):
            continue
        with open(p, encoding="utf-8") as f:
            rows.extend(json.loads(line) for line in f if line.strip())
    if rows:
        return rows, broad, "runs_*.jsonl"

    # GitHub does not currently commit raw runs_*.jsonl files, so the committed
    # aggregate JSON is the reproducible fallback.
    aggregate = OUTPUT_DIR / "multi_model_results_v2.json"
    if aggregate.exists():
        rows = json.loads(aggregate.read_text(encoding="utf-8"))
        return rows, broad, "multi_model_results_v2.json"

    return [], broad, "none"


def summarize(rows: list[dict], label: str, weights: dict[str, float] | None = None, verbose: bool = True) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["condition"]].append(row)

    out = {}
    for condition in ["A", "B", "C", "D"]:
        items = grouped.get(condition, [])
        if not items:
            continue
        avg_access = sum(len(set(r.get("accessed_ids", []))) for r in items) / len(items)
        realized = (
            sum(
                sum(realized_sensitive(iid, condition, weights) for iid in set(r.get("accessed_ids", [])))
                for r in items
            )
            / len(items)
        )
        success = sum(1 for r in items if r.get("task_success")) / len(items)
        out[condition] = {
            "n": len(items),
            "avg_access": round(avg_access, 2),
            "realized_sensitive": round(realized, 2),
            "success_rate": round(success, 3),
        }

    if verbose:
        print(f"\n=== {label} ===")
        print(f"{'cond':4s} | n   | avg_access | realized_sensitive | success")
        for condition, values in out.items():
            print(
                f"{condition:4s} | {values['n']:3d} | {values['avg_access']:10.2f} | "
                f"{values['realized_sensitive']:18.2f} | {values['success_rate'] * 100:6.1f}%"
            )
    return out


def sensitivity_analysis(rows: list[dict], broad: set[str]) -> dict:
    narrow_rows = [r for r in rows if r["scenario"] not in broad]
    broad_rows = [r for r in rows if r["scenario"] in broad]
    result = {}
    for name, weights in WEIGHT_SCHEMES.items():
        result[name] = {
            "weights": weights,
            "narrow": summarize(narrow_rows, f"narrow/{name}", weights=weights, verbose=False),
            "broad": summarize(broad_rows, f"broad/{name}", weights=weights, verbose=False),
        }
    return result


def plot_realized(narrow: dict, broad: dict) -> Path:
    conditions = ["A", "B", "C", "D"]
    narrow_values = [narrow.get(c, {}).get("realized_sensitive", 0) for c in conditions]
    broad_values = [broad.get(c, {}).get("realized_sensitive", 0) for c in conditions]

    x = range(len(conditions))
    width = 0.38
    fig, ax = plt.subplots(figsize=(7.5, 4.3))
    ax.bar([i - width / 2 for i in x], narrow_values, width, label="좁은 업무 s1-s40", color="#4C78A8")
    ax.bar([i + width / 2 for i in x], broad_values, width, label="광범위 업무 s41-s48", color="#E45756")
    for i, value in enumerate(broad_values):
        ax.text(i + width / 2, value, f"{value:.1f}", ha="center", va="bottom", fontsize=9)
    ax.set_xticks(list(x))
    ax.set_xticklabels(conditions)
    ax.set_ylabel("실현 민감노출 점수")
    ax.set_title("실현 민감노출: B는 프롬프트만, C/D는 필드 최소권한")
    ax.legend()
    plt.tight_layout()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = FIG_DIR / "fig_realized_exposure.png"
    plt.savefig(out, dpi=180)
    plt.close()
    return out


def plot_sensitivity(sensitivity: dict) -> Path:
    schemes = list(sensitivity.keys())
    conditions = ["A", "B", "C", "D"]
    width = 0.18
    x = list(range(len(schemes)))
    offsets = [-1.5 * width, -0.5 * width, 0.5 * width, 1.5 * width]
    colors = {"A": "#F58518", "B": "#BAB0AC", "C": "#54A24B", "D": "#4C78A8"}

    fig, ax = plt.subplots(figsize=(9.2, 4.4))
    for offset, condition in zip(offsets, conditions):
        values = [sensitivity[s]["broad"].get(condition, {}).get("realized_sensitive", 0) for s in schemes]
        ax.bar([i + offset for i in x], values, width, label=condition, color=colors[condition])
    ax.set_xticks(x)
    ax.set_xticklabels(schemes, rotation=15)
    ax.set_ylabel("광범위 업무 실현 민감노출")
    ax.set_title("가중치 민감도 분석: C/D 감소 방향이 유지되는가")
    ax.legend(ncol=4)
    plt.tight_layout()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = FIG_DIR / "fig_weight_sensitivity.png"
    plt.savefig(out, dpi=180)
    plt.close()
    return out


def main() -> None:
    rows, broad, source = load_rows_and_broad_set()
    if not rows:
        print("no runs found.")
        return

    narrow_rows = [r for r in rows if r["scenario"] not in broad]
    broad_rows = [r for r in rows if r["scenario"] in broad]
    narrow = summarize(narrow_rows, "좁은 업무 s1-s40", weights=DEFAULT_WEIGHTS)
    broad_summary = summarize(broad_rows, "광범위 업무 s41-s48", weights=DEFAULT_WEIGHTS)
    sensitivity = sensitivity_analysis(rows, broad)

    SUMMARY.write_text(
        json.dumps(
            {
                "source": source,
                "narrow": narrow,
                "broad": broad_summary,
                "weights": DEFAULT_WEIGHTS,
                "note": "B is prompt-only and therefore uses A-like field exposure when an item is accessed.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    SENSITIVITY_SUMMARY.write_text(json.dumps(sensitivity, ensure_ascii=False, indent=2), encoding="utf-8")

    fig1 = plot_realized(narrow, broad_summary)
    fig2 = plot_sensitivity(sensitivity)
    print("\nSource:", source)
    print("Figure:", fig1)
    print("Sensitivity figure:", fig2)
    print("Summary:", SUMMARY)
    print("Sensitivity:", SENSITIVITY_SUMMARY)


if __name__ == "__main__":
    main()
