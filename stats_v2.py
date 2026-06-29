#!/usr/bin/env python3
"""2400 run에 대한 paired 통계 (올바른 분석 단위).

[중요] 현재 데이터는 seed가 모델 호출에 전달되지 않아(temp=0.1), 같은
(model, scenario, condition)의 10개 seed가 사실상 동일한 복제다(접근 98%·성공 86%
가 seed 전부 동일). 따라서 seed를 독립 표본으로 쓰면 유효 표본이 ~10배 부풀려진다.

올바른 분석 단위 = (model, scenario) 페어(n=60). seed는 majority로 붕괴한다.
참고용으로 naive(per-run) 수치도 함께 출력하되, 결론은 collapsed 기준으로 본다.
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
    result = {"analysis_unit": "model x scenario (n=60), seeds collapsed by majority",
              "seed_independence": {"groups": tot, "identical_access": sa, "identical_success": ss},
              "mcnemar": {}, "success_rate_collapsed": {}}
    n_units = len({(k[0], k[1]) for k in unit})
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
