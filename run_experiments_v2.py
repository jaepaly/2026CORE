#!/usr/bin/env python3
"""v2 실험 배치 실행기: A/B/C 조건 x 시나리오 x 모델 x seed."""
import os
import json
import time
import itertools
import sys
import subprocess
from datetime import datetime
from llm_agent_v2 import run_agent_loop, log_run

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
RESULTS_JSON = os.path.join(OUTPUT_DIR, f"multi_model_results_v2_{sys.argv[1] if len(sys.argv)>1 else 'all'}.json")

MODELS = ["qwen3:8b", "llama3.1:8b", "qwen2.5:7b"]
CONDITIONS = ["A", "B", "C"]
SEEDS = list(range(10))
MAX_TURNS = 4

MODEL_FILTER = sys.argv[1] if len(sys.argv) > 1 else None
if MODEL_FILTER:
    MODELS = [m for m in MODELS if MODEL_FILTER in m]


def load_scenario_ids():
    path = os.path.join(DATA_DIR, "scenarios_v2.json")
    if not os.path.exists(path):
        path = os.path.join(DATA_DIR, "scenarios.json")
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
                done.add((r.get("model"), r.get("scenario"), r.get("condition"), r.get("seed")))
            except Exception:
                pass
    return done


def main():
    model_label = MODEL_FILTER or "all"
    runs_jsonl = os.path.join(OUTPUT_DIR, f"runs_{model_label.replace(':','_')}.jsonl")
    scenario_ids = load_scenario_ids()
    existing_done = load_existing_done(runs_jsonl)
    start = time.time()
    rows = []
    planned = list(itertools.product(MODELS, scenario_ids, CONDITIONS, SEEDS))
    # skip already done
    todo = [p for p in planned if p not in existing_done]
    print(f"[{model_label}] total planned={len(planned)}, already_done={len(existing_done)}, todo={len(todo)}", flush=True)
    for i, (model, scenario_id, condition, seed) in enumerate(todo, start=1):
        label = f"{model} | {scenario_id} | {condition} | seed{seed}"
        print(f"[{i}/{len(todo)}] {label}", flush=True)
        try:
            run = run_agent_loop(
                model_name=model,
                scenario_id=scenario_id,
                condition=condition,
                max_turns=MAX_TURNS,
                seed=seed,
            )
        except Exception as e:
            run = {"error": str(e), "model": model, "scenario": scenario_id, "condition": condition, "seed": seed}
        log_run(run, filename=runs_jsonl)
        rows.append({
            "model": run.get("model"),
            "scenario": run.get("scenario"),
            "condition": run.get("condition"),
            "seed": run.get("seed"),
            "task_success": run.get("task_success", False),
            "accessed_ids_count": len(run.get("accessed_ids", [])),
            "malicious_accessed_count": len(run.get("malicious_accessed", [])),
            "attack_compliance": run.get("attack_compliance", False),
            "attack_leakage": run.get("attack_leakage", False),
            "latency_s": run.get("latency_s", 0),
            "tool_call_count": run.get("tool_call_count", 0),
            "turns": run.get("turns", 0),
        })
        if i % 20 == 0:
            elapsed = time.time() - start
            print(f"  ... {i}/{len(todo)} runs done ({elapsed:.1f}s)", flush=True)
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f"Done. new={len(rows)} runs in {time.time()-start:.1f}s")
    print(f"Results -> {RESULTS_JSON}")

    # self-destruct cleanup
    if len(sys.argv) > 2 and sys.argv[1] == "--cleanup":
        job_id = sys.argv[2]
        print(f"Self-removing cronjob {job_id}...", flush=True)
        try:
            subprocess.run(["hermes", "cronjob", "remove", job_id], check=False)
            print("cleanup done")
        except Exception as e:
            print("cleanup failed:", e)


if __name__ == "__main__":
    main()
