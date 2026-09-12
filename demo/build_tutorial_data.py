#!/usr/bin/env python3
"""첫 진입 튜토리얼 데이터 생성.

튜토리얼은 4단계로 "같은 요청, 허용 필드 목록만 다름 -> 민감정보가 사라짐"을
보여준다. 그 4단계가 지어낸 예시이면 이 연구의 최대 강점(실측)을 스스로 버리는
셈이므로, 화면에 나오는 값은 전부 커밋된 산출물에서 뽑는다.

  - 어떤 필드가 전달/제거됐는가 : experiments/main-*/runs.jsonl 의 delivery_events
  - 그 필드의 실제 값          : data/contacts.json (공개 합성 데이터)
  - 업무 요청 문구             : demo/replay_index.json

runs.jsonl 에는 원문이 없고 필드 경로·레코드 ID·해시만 있다. 값은 공개 합성
데이터와 조인해 복원한다 — demo/replay.js 가 쓰는 방식과 같다.

    python demo/build_tutorial_data.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEMO = Path(__file__).resolve().parent
OUT = DEMO / "tutorial_data.json"

# v3_s1 / qwen3:8b 를 고른 이유: A 와 C 의 1턴 requested_args_sha256 이 같다.
# 즉 모델이 글자 그대로 같은 도구 호출을 했고 달라진 것은 돌아온 응답뿐이다.
# 튜토리얼이 주장하려는 바로 그 대조가 산출물 안에서 그대로 성립한다.
EXPERIMENT = "experiments/main-qwen3-8b"
SCENARIO = "v3_s1"
TURN = 1

SENSITIVE_LABEL = {
    "phone": "연락처",
    "notes": "개인 메모",
}


def load_runs(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def event_for(run: dict, turn: int) -> dict:
    for event in run.get("delivery_events", []):
        if event.get("turn") == turn:
            return event
    raise SystemExit(f"turn {turn} not found in {run['run_id']}")


def strip_list_prefix(path: str) -> str:
    """'[].phone' -> 'phone'. search_* 는 리스트를 돌려주므로 경로에 [] 가 붙는다."""
    return path.split(".", 1)[1] if path.startswith("[].") else path


def main() -> None:
    runs = load_runs(ROOT / EXPERIMENT / "runs.jsonl")
    picked = {}
    for condition in ("A", "C"):
        matches = [
            r for r in runs
            if r["scenario"] == SCENARIO and r["condition"] == condition and r["seed"] == 0
        ]
        if not matches:
            raise SystemExit(f"no run for {SCENARIO}/{condition}")
        picked[condition] = matches[0]

    events = {c: event_for(r, TURN) for c, r in picked.items()}

    if events["A"]["requested_args_sha256"] != events["C"]["requested_args_sha256"]:
        raise SystemExit(
            "A 와 C 의 요청 인자 해시가 다릅니다. 튜토리얼은 '같은 요청'을 주장하므로 "
            "이 전제가 깨지면 만들지 않습니다."
        )

    record_id = events["A"]["delivered_record_ids"][0]
    contacts = {c["id"]: c for c in json.loads((ROOT / "data" / "contacts.json").read_text(encoding="utf-8"))}
    record = contacts[record_id]

    scenarios = json.loads((DEMO / "replay_index.json").read_text(encoding="utf-8"))["scenarios"]
    task = next(s for s in scenarios if s["id"] == SCENARIO)["task"]

    sensitive = {strip_list_prefix(p) for p in events["A"]["delivered_sensitive_field_paths"]}
    delivered_a = [strip_list_prefix(p) for p in events["A"]["delivered_field_paths"]]
    delivered_c = [strip_list_prefix(p) for p in events["C"]["delivered_field_paths"]]
    removed_c = [strip_list_prefix(p) for p in events["C"]["removed_field_paths"]]

    fields = []
    for name in delivered_a:
        fields.append({
            "field": name,
            "value": record.get(name),
            "sensitive": name in sensitive,
            "sensitiveLabel": SENSITIVE_LABEL.get(name),
            "keptUnderPolicy": name in delivered_c,
        })

    payload = {
        "_source": "demo/build_tutorial_data.py — 손으로 적은 값 없음",
        "task": task,
        "scenario": SCENARIO,
        "model": picked["A"]["model"],
        "tool": events["A"]["tool_name"],
        "recordId": record_id,
        "recordName": record.get("name"),
        "requestArgsSha256": events["A"]["requested_args_sha256"],
        "fields": fields,
        "allowedFieldPaths": sorted(f"{events['C']['tool_name']}.{n}" for n in delivered_c),
        "removedUnderPolicy": sorted(removed_c),
        "counts": {
            "sensitiveWithout": picked["A"]["excess_sensitive_field_count"],
            "sensitiveWith": picked["C"]["excess_sensitive_field_count"],
        },
        "provenance": {
            "experiment": EXPERIMENT,
            "runIdWithout": picked["A"]["run_id"],
            "runIdWith": picked["C"]["run_id"],
            "projectionSourceWithout": events["A"]["projection_source"],
            "projectionSourceWith": events["C"]["projection_source"],
        },
    }

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  요청 해시 일치: {payload['requestArgsSha256'][:16]}…")
    print(f"  민감 필드 {payload['counts']['sensitiveWithout']} -> {payload['counts']['sensitiveWith']}")
    print(f"  필드 {len(fields)}개 중 정책 통과 {len(delivered_c)}개")


if __name__ == "__main__":
    main()
