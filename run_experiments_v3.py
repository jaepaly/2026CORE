#!/usr/bin/env python3
"""v3 실험 배치 실행기: 접근 범위(access scope) 중심.

축(arm) = (policy, tool_mode, framing)
- coarse(read_all) 상한선 + granular 정책(A/C) x 프레이밍(none/must/safe/authorized)
- 기존 v2 런(runs_qwen3.jsonl 등)은 건드리지 않고 runs_v3_*.jsonl 에 별도 기록.

사용:
  python run_experiments_v3.py qwen3            # 단일 모델, seed 5개(기본)
  python run_experiments_v3.py qwen3 --seeds 10 # seed 10개
"""
import os
import json
import time
import itertools
import sys
from llm_agent_v2 import run_agent_loop, log_run

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

MODELS = ["qwen3:8b", "llama3.1:8b", "qwen2.5:7b"]
MAX_TURNS = 4

# 실험 arm: (policy, tool_mode, framing)
ARMS = [
    # 위험 상한선: read_all 통째 반환 (도구 입도 대조군)
    ("A", "coarse", "none"),
    # granular 기준선 + 프레이밍 (정책 A: 방어 없음)
    ("A", "granular", "none"),
    ("A", "granular", "must"),
    ("A", "granular", "safe"),
    ("A", "granular", "authorized"),
    # granular + 정책 미들웨어 C + 프레이밍 (프레이밍을 정책이 막는가)
    ("C", "granular", "none"),
    ("C", "granular", "must"),
    ("C", "granular", "safe"),
    ("C", "granular", "authorized"),
]


def parse_args():
    model_filter = None
    seeds = 5
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--seeds":
            seeds = int(args[i + 1]); i += 2
        else:
            model_filter = args[i]; i += 1
    return model_filter, list(range(seeds))


def load_scenario_ids():
    path = os.path.join(DATA_DIR, "scenarios_v2.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [s["id"] for s in data["scenarios"]]


def load_existing_done(runs_jsonl: str) -> set:
    done = set()
    if not os.path.exists(runs_jsonl):
        return done
    with open(runs_jsonl, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                done.add((r.get("model"), r.get("scenario"), r.get("condition"),
                          r.get("tool_mode"), r.get("framing"), r.get("seed")))
            except Exception:
                pass
    return done


def main():
    model_filter, seeds = parse_args()
    models = [m for m in MODELS if model_filter in m] if model_filter else MODELS
    model_label = model_filter or "all"
    runs_jsonl = os.path.join(OUTPUT_DIR, f"runs_v3_{model_label.replace(':','_')}.jsonl")
    scenario_ids = load_scenario_ids()
    existing = load_existing_done(runs_jsonl)

    planned = []
    for model, sid, (policy, tool_mode, framing), seed in itertools.product(
        models, scenario_ids, ARMS, seeds
    ):
        planned.append((model, sid, policy, tool_mode, framing, seed))
    todo = [p for p in planned if (p[0], p[1], p[2], p[3], p[4], p[5]) not in existing]
    print(f"[{model_label}] arms={len(ARMS)} scenarios={len(scenario_ids)} seeds={len(seeds)} "
          f"| planned={len(planned)} done={len(existing)} todo={len(todo)}", flush=True)

    start = time.time()
    for i, (model, sid, policy, tool_mode, framing, seed) in enumerate(todo, start=1):
        label = f"{model} | {sid} | {policy}/{tool_mode}/{framing} | s{seed}"
        print(f"[{i}/{len(todo)}] {label}", flush=True)
        try:
            run = run_agent_loop(
                model_name=model, scenario_id=sid, condition=policy,
                max_turns=MAX_TURNS, seed=seed,
                tool_mode=tool_mode, framing=framing,
            )
        except Exception as e:
            run = {"error": str(e), "model": model, "scenario": sid,
                   "condition": policy, "tool_mode": tool_mode, "framing": framing, "seed": seed}
        log_run(run, filename=runs_jsonl)
        if i % 20 == 0:
            print(f"  ... {i}/{len(todo)} done ({time.time()-start:.0f}s)", flush=True)

    print(f"Done. new={len(todo)} runs in {time.time()-start:.0f}s -> {runs_jsonl}")


if __name__ == "__main__":
    main()
