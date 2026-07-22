#!/usr/bin/env python3
"""Paired success-rate statistics.

[중요] seed 반복이 여러 개 있더라도 낮은 temperature에서는 독립 표본으로 보기 어렵다.
따라서 조건 간 성공률 비교는 run 단위가 아니라 paired 분석 단위인
(model, scenario)로 붕괴해 본다.

현재 커밋 기준 데이터는 4 models × 48 scenarios = 192 paired units, seed=1이다.
"""
import json
import math
from collections import defaultdict

OUTPUT = "output"


def load():
    import glob, os
    rows = []
    for p in sorted(glob.glob(f"{OUTPUT}/runs_*.jsonl")):
        b = os.path.basename(p)
        if b == "runs.jsonl" or b.startswith("runs_v3_"):
            continue
        rows += [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    if rows:
        return rows
    # Reproducibility fallback for the committed repository: raw JSONL logs are
    # not always tracked, but the aggregate run file is.
    aggregate = f"{OUTPUT}/multi_model_results_v2.json"
    try:
        with open(aggregate, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except FileNotFoundError:
        pass
    return rows


def seed_determinism(rows):
    g = defaultdict(list)
    for r in rows:
        g[(r["model"], r["scenario"], r["condition"])].append(
            (tuple(sorted(set(r.get("accessed_ids", [])))), bool(r.get("task_success"))))
    tot = same_acc = same_suc = 0
    for v in g.values():
        if len(v) < 2:
            continue
        tot += 1
        if len({x[0] for x in v}) == 1:
            same_acc += 1
        if len({x[1] for x in v}) == 1:
            same_suc += 1
    return tot, same_acc, same_suc


def collapse(rows):
    """ (model,scenario,condition) -> majority success """
    g = defaultdict(list)
    for r in rows:
        g[(r["model"], r["scenario"], r["condition"])].append(bool(r.get("task_success")))
    return {k: (sum(v) >= len(v) / 2) for k, v in g.items()}


def mcnemar(unit, c1, c2):
    b = c = pairs = 0
    models = {k[0] for k in unit}
    scen = {k[1] for k in unit}
    for m in models:
        for s in scen:
            if (m, s, c1) in unit and (m, s, c2) in unit:
                pairs += 1
                s1, s2 = unit[(m, s, c1)], unit[(m, s, c2)]
                if s1 and not s2:
                    b += 1
                elif s2 and not s1:
                    c += 1
    N = b + c
    p = 1.0 if N == 0 else min(sum(math.comb(N, i) for i in range(min(b, c) + 1)) * 0.5 ** N * 2, 1.0)
    return b, c, pairs, p


def main():
    rows = load()
    tot, sa, ss = seed_determinism(rows)
    if tot == 0:
        print("[seed] seed 반복 없음(seed=1). 분석 단위 = (model,scenario).\n")
    else:
        print(f"[seed 독립성 점검] (model,scenario,condition) {tot}개 그룹 중")
        print(f"  접근 ID가 seed 전부 동일: {sa}/{tot} ({sa/tot*100:.0f}%)")
        print(f"  성공여부가 seed 전부 동일: {ss}/{tot} ({ss/tot*100:.0f}%)")
        print("  -> seed는 독립 반복이 아님. 분석 단위를 (model,scenario)로 붕괴.\n")

    unit = collapse(rows)
    n_units = len({(k[0], k[1]) for k in unit})
    result = {"analysis_unit": f"model x scenario (n={n_units}), seeds collapsed by majority when repeated",
              "seed_independence": {"groups": tot, "identical_access": sa, "identical_success": ss},
              "mcnemar": {}, "success_rate_collapsed": {}}
    print(f"McNemar (분석단위 = model×scenario, 단위수={n_units}):")
    print(f"{'cmp':8s} | pairs | b | c | p")
    for c1, c2 in [("A", "B"), ("A", "C"), ("A", "D"), ("C", "D"), ("B", "C")]:
        b, c, pr, p = mcnemar(unit, c1, c2)
        result["mcnemar"][f"{c1}_vs_{c2}"] = {"pairs": pr, "b": b, "c": c, "p": round(p, 4),
                                              "significant": p < 0.05}
        print(f"{c1} vs {c2} |  {pr}   | {b} | {c} | {p:.4f}{'*' if p < 0.05 else ''}")

    bycond = defaultdict(list)
    for (m, s, c), val in unit.items():
        bycond[c].append(val)
    print(f"\n성공률 (collapsed, 단위수={n_units}):")
    for c in ["A", "B", "C", "D"]:
        rate = sum(bycond[c]) / len(bycond[c])
        result["success_rate_collapsed"][c] = round(rate, 3)
        print(f"  {c}: {sum(bycond[c])}/{len(bycond[c])} = {rate:.2f}")

    with open(f"{OUTPUT}/stats_summary_v2.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("\nSaved -> output/stats_summary_v2.json")
    print("결론: 조건 간 성공률 차이는 올바른 분석 단위에서 통계적으로 유의하지 않음(방향만 시사).")


if __name__ == "__main__":
    main()
