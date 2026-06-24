#!/usr/bin/env python3
"""3개 LLM 모델 × 4시나리오 × 10회 반복 실험"""
from experiment import SCENARIO_MAP, run_llm_access, compute_metrics, SCENARIO_MAP
from llm_agent import MODEL_NAME
import json, time
import os

MODELS = ["qwen3:8b", "llama3.1:8b", "qwen2.5:7b"]
REPEAT = 10
RESULTS = []

for model in MODELS:
    for sid in SCENARIO_MAP:
        print(f"[{model}] {sid} start")
        start = time.time()
        accessed, inc, meta = run_llm_access(repeat=REPEAT, scenario_id=sid, model_name=model)
        m = compute_metrics(accessed, inc)
        elapsed = time.time() - start
        row = {
            "model": model,
            "scenario": sid,
            "total_items_accessed": m["total_items_accessed"],
            "ea": m["exposure_area"],
            "avg_sensitivity": m["avg_sensitivity"],
            "avg_relevance": m["avg_relevance"],
            "irrelevant_ratio": m["irrelevant_ratio"],
            "incident_detected": m["incident"]["detected"],
            "malicious_email_ids": m["incident"].get("malicious_email_id", []),
            "avg_latency_s": meta.get("avg_latency_s", -1),
            "elapsed_s": round(elapsed, 2),
        }
        RESULTS.append(row)
        print(f"[{model}] {sid} done: EA={m['exposure_area']}, items={m['total_items_accessed']}, latency={meta.get('avg_latency_s', -1)}s")

with open("output/multi_model_results.json", "w", encoding="utf-8") as f:
    json.dump(RESULTS, f, ensure_ascii=False, indent=2)
print("saved output/multi_model_results.json")
