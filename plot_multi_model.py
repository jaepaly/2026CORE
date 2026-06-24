#!/usr/bin/env python3
"""모델별 4시나리오 결과 비교 시각화"""
import json
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

with open("output/multi_model_results.json", encoding="utf-8") as f:
    rows = json.load(f)

models = ["qwen3:8b", "llama3.1:8b", "qwen2.5:7b"]
scenarios = ["s1", "s2", "s3", "s4"]
scenario_labels = ["S1\n회의 일정 조율", "S2\n회의실 예약", "S3\n문서 검토", "S4\n주간 메일 요약"]

# 1) 모델별 EA 비교 (그룹형 bar)
fig, ax = plt.subplots(figsize=(10, 6))
x = np.arange(len(scenarios))
width = 0.25
colors = ["#3498db", "#2ecc71", "#e67e22"]
for i, model in enumerate(models):
    vals = [next(r["ea"] for r in rows if r["model"] == model and r["scenario"] == s) for s in scenarios]
    ax.bar(x + i*width, vals, width, label=model, color=colors[i], edgecolor="black", linewidth=0.5)
ax.set_ylabel("Exposure Area", fontsize=12)
ax.set_title("모델별 시나리오 Exposure Area 비교", fontsize=14)
ax.set_xticks(x + width)
ax.set_xticklabels(scenario_labels)
ax.legend(title="모델", loc="upper left")
ax.grid(axis="y", linestyle="--", alpha=0.5)
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)
plt.tight_layout()
plt.savefig("output/fig9_model_compare.png", dpi=200)
plt.close()

# 2) 모델별 평균 EA 라인차트
fig, ax = plt.subplots(figsize=(9, 5))
for i, model in enumerate(models):
    vals = [next(r["ea"] for r in rows if r["model"] == model and r["scenario"] == s) for s in scenarios]
    ax.plot(scenario_labels, vals, marker="o", linewidth=2, label=model, color=colors[i])
    for j, v in enumerate(vals):
        ax.annotate(f"{v:.2f}", (scenario_labels[j], v), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)
ax.set_ylabel("Exposure Area", fontsize=12)
ax.set_title("모델별 평균 Exposure Area 추이", fontsize=13)
ax.legend(title="모델")
ax.grid(linestyle="--", alpha=0.5)
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)
plt.tight_layout()
plt.savefig("output/fig10_model_trend.png", dpi=200)
plt.close()

# 3) 모델별 인시던트 히트맵
fig, ax = plt.subplots(figsize=(8, 4))
incident_matrix = np.zeros((len(models), len(scenarios)), dtype=int)
for mi, model in enumerate(models):
    for si, s in enumerate(scenarios):
        r = next((r for r in rows if r["model"] == model and r["scenario"] == s), None)
        incident_matrix[mi, si] = 1 if r and r["incident_detected"] else 0
im = ax.imshow(incident_matrix, cmap="RdYlGn_r", aspect="auto", vmin=0, vmax=1)
ax.set_xticks(np.arange(len(scenarios)))
ax.set_xticklabels(scenario_labels)
ax.set_yticks(np.arange(len(models)))
ax.set_yticklabels(models)
ax.set_title("모델별 프롬�프트 인젝션 인시던트 발생 (1=발생)", fontsize=12)
for i in range(len(models)):
    for j in range(len(scenarios)):
        ax.text(j, i, "O" if incident_matrix[i, j] else "X", ha="center", va="center", color="black", fontsize=14)
plt.tight_layout()
plt.savefig("output/fig11_incident_heatmap.png", dpi=200)
plt.close()

print("model visuals saved: fig9, fig10, fig11")
