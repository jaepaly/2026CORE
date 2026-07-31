#!/usr/bin/env python3
"""Pilot candidate models before the v3 main study.

    python run_model_pilot_v3.py --experiment-dir experiments/pilot \
        --model qwen3:8b --model llama3.1:8b --model mistral:7b

The protocol admits only models that demonstrably emit tool calls
(`protocols/v3_protocol.json: model_pilot_gate`).  Without this gate a model that
never calls a tool records "accessed nothing", which reads as excellent privacy
behaviour but is really a format failure -- the exact trap v2 fell into, where
`mistral:7b` scored 0% tool-calls and `qwen2.5:14b` 12%.

The pilot runs the **neutral** arm (condition A prompt, no projection) so a
model is judged on tool-calling ability alone, never on how it reacts to a
minimisation instruction.  Exclusions are written out with their numbers so the
paper can state who was dropped and why.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import requests

from ollama_v3_adapter import make_ollama_model_step
from prompt_v3 import DEFAULT_TOOL_NAMES, build_system_prompt
from protocol_v3 import load_protocol
from scenario_review_v3 import select_approved_scenarios
from tools_v3 import TOOLS_SCHEMA

ROOT = Path(__file__).resolve().parent
DEFAULT_REVIEW_CSV = ROOT / "data" / "scenario_review_v3.csv"
DEFAULT_PROTOCOL = ROOT / "protocols" / "v3_protocol.json"
OLLAMA_URL = "http://localhost:11434/api/chat"


def probe_model(*, model_step, tasks: list[str], system_prompt: str) -> dict:
    """One turn per task; count tool-call emission and transport/parse faults."""
    valid_tool_calls = 0
    errors = 0
    details = []
    for task in tasks:
        messages = [{"role": "system", "content": system_prompt},
                    {"role": "user", "content": task}]
        try:
            response = model_step(messages)
        except Exception as error:  # transport, HTTP status, or response shape
            errors += 1
            details.append({"task": task[:40], "outcome": "error",
                            "error_type": type(error).__name__})
            continue
        calls = response.get("tool_calls") or []
        named = [c for c in calls if isinstance(c, dict) and c.get("name")]
        if named:
            valid_tool_calls += 1
            details.append({"task": task[:40], "outcome": "tool_call",
                            "tools": [c["name"] for c in named]})
        else:
            details.append({"task": task[:40], "outcome": "no_tool_call"})

    total = len(tasks)
    return {
        "probes": total,
        "valid_tool_call_rate": valid_tool_calls / total if total else 0.0,
        "error_rate": errors / total if total else 0.0,
        "details": details,
    }


def judge(result: dict, gate: dict) -> tuple[bool, list[str]]:
    reasons = []
    if result["valid_tool_call_rate"] < gate["min_valid_tool_call_rate"]:
        reasons.append(
            f"valid tool-call rate {result['valid_tool_call_rate']:.0%} < "
            f"{gate['min_valid_tool_call_rate']:.0%}"
        )
    if result["error_rate"] > gate["max_server_or_parser_error_rate"]:
        reasons.append(
            f"error rate {result['error_rate']:.0%} > "
            f"{gate['max_server_or_parser_error_rate']:.0%}"
        )
    return (not reasons), reasons


def write_report(experiment_dir: Path, gate: dict, results: dict) -> None:
    experiment_dir.mkdir(parents=True, exist_ok=True)
    (experiment_dir / "model_pilot.json").write_text(
        json.dumps({"gate": gate, "models": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# v3 모델 파일럿 결과", "",
        f"게이트: valid tool-call ≥ {gate['min_valid_tool_call_rate']:.0%}, "
        f"error ≤ {gate['max_server_or_parser_error_rate']:.0%}",
        "",
        "중립 조건(A 프롬프트, projection 없음)으로만 측정했다. 도구 호출 능력만 보기 위해서이며,",
        "최소화 지시에 어떻게 반응하는지는 파일럿의 판단 근거가 아니다.",
        "",
        "| 모델 | 시도 | valid tool-call | error | 판정 | 사유 |",
        "|---|---:|---:|---:|---|---|",
    ]
    for name, entry in results.items():
        verdict = "포함" if entry["included"] else "**제외**"
        lines.append(
            f"| `{name}` | {entry['probes']} | {entry['valid_tool_call_rate']:.0%} | "
            f"{entry['error_rate']:.0%} | {verdict} | {'; '.join(entry['reasons']) or '—'} |"
        )
    included = [n for n, e in results.items() if e["included"]]
    lines += ["", f"본 실험 투입 모델: {', '.join(f'`{n}`' for n in included) or '없음'}"]
    (experiment_dir / "model_inclusion.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="v3 model pilot gate")
    parser.add_argument("--experiment-dir", required=True)
    parser.add_argument("--model", action="append", required=True)
    parser.add_argument("--review-csv", default=str(DEFAULT_REVIEW_CSV))
    parser.add_argument("--protocol", default=str(DEFAULT_PROTOCOL))
    parser.add_argument("--probes", type=int, default=10, help="tasks per model")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--think", action="store_true")
    parser.add_argument("--num-predict", type=int, default=1000)
    args = parser.parse_args(argv)

    gate = load_protocol(args.protocol)["model_pilot_gate"]
    with Path(args.review_csv).open(encoding="utf-8", newline="") as handle:
        rows = select_approved_scenarios(list(csv.DictReader(handle)))
    tasks = [row["task"] for row in rows[: args.probes]]
    if not tasks:
        print("no approved scenarios to probe")
        return 2

    system_prompt = build_system_prompt(condition="A", tool_names=DEFAULT_TOOL_NAMES)
    results = {}
    for name in args.model:
        step = make_ollama_model_step(
            request_post=requests.post, model_name=name, tools=TOOLS_SCHEMA,
            url=OLLAMA_URL, seed=0, temperature=args.temperature, think=args.think,
            num_predict=args.num_predict,
        )
        result = probe_model(model_step=step, tasks=tasks, system_prompt=system_prompt)
        included, reasons = judge(result, gate)
        results[name] = {**result, "included": included, "reasons": reasons}
        print(f"{name:16s} tool-call {result['valid_tool_call_rate']:.0%}  "
              f"error {result['error_rate']:.0%}  -> {'포함' if included else '제외'}"
              f"{'  (' + '; '.join(reasons) + ')' if reasons else ''}", flush=True)

    write_report(Path(args.experiment_dir), gate, results)
    included = [n for n, e in results.items() if e["included"]]
    print(f"\n포함 {len(included)}/{len(results)} -> {Path(args.experiment_dir)}/model_inclusion.md")
    return 0 if included else 1


if __name__ == "__main__":
    raise SystemExit(main())
