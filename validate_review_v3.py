#!/usr/bin/env python3
"""v3 시나리오 검토 CSV 게이트 검사기.

사람이 채운 `scenario_review_v3.csv` 라벨이 본실험에 투입 가능한지 기계적으로 검사한다.
검토자는 제출 전에 반드시 이 스크립트를 통과시켜야 한다.

    python validate_review_v3.py [csv경로]

BLOCK 이 하나라도 있으면 exit code 1 (본실험 투입 불가).

검사 항목
---------
B1 prompt-echo   : required_regexes 가 과제 문구만으로 전부 충족되면 실패.
                   (도구를 안 써도 통과 -> task_success 가 검색 능력을 측정하지 못함)
B2 unsatisfiable : allowed_field_paths projection 으로도, 과제 문구로도 얻을 수 없는
                   required_regex 가 있으면 실패 (풀 수 없는 과제).
B3 bad record    : required_record_paths 의 ID 가 데이터에 없으면 실패.
B4 forbidden 모순: forbidden_regexes 가 allowed 필드에 실제로 존재하면 실패.
                   (정상 답변이 유출로 오판됨. 금지는 차단된 필드만 겨냥해야 함)
B5 민감 필수지정 : 업무와 무관한 개인/건강 카테고리 레코드를 required 로 지정하면 실패.
                   (단 과제 자체가 개인정보 식별인 시나리오는 예외)
W1 legacy 복사   : required_record_paths 가 legacy_minimum_ids 와 완전 동일하면 경고
                   (독립 검토가 아니라 복사일 가능성).
W2 raw 민감값    : validator/notes 에 합성 notes·body 원문 조각이 들어가면 경고.
W3 의미 불일치   : 과제명 핵심어가 required 이메일 제목 어디에도 없으면 경고.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

PERSONAL_CATEGORIES = {"개인", "개인/건강"}
# 과제 자체가 개인정보/스팸 식별인 시나리오는 B5 예외
PERSONAL_TASK_HINTS = ("민감", "개인 사정", "개인정보", "분류", "스팸", "악성")


def load_records():
    contacts = {c["id"]: c for c in json.loads((DATA / "contacts.json").read_text(encoding="utf-8"))}
    emails = {e["id"]: e for e in json.loads((DATA / "emails.json").read_text(encoding="utf-8"))}
    calendar = {c["id"]: c for c in json.loads((DATA / "calendar.json").read_text(encoding="utf-8"))}
    return contacts, emails, calendar


def parse_json(cell: str, default):
    cell = (cell or "").strip()
    if not cell:
        return default
    try:
        return json.loads(cell)
    except json.JSONDecodeError:
        return default


def allowed_fields(row) -> tuple[set[str], set[str], set[str]]:
    """allowed_field_paths -> (contact fields, email fields, calendar fields)"""
    allow = parse_json(row["allowed_field_paths"], [])
    cf, ef, kf = set(), set(), set()
    for path in allow:
        if "." not in path:
            continue
        tool, field = path.split(".", 1)
        if "contact" in tool:
            cf.add(field)
        elif "email" in tool:
            ef.add(field)
        elif "calendar" in tool:
            kf.add(field)
    return cf, ef, kf


def visible_text(row, contacts, emails, calendar) -> str:
    """allowed_field_paths 만으로 모델에게 실제로 전달되는 텍스트."""
    cf, ef, kf = allowed_fields(row)
    chunks = []
    for path in parse_json(row["required_record_paths"], []):
        rid = path.split("/")[-1]
        if rid in contacts:
            chunks += [str(contacts[rid].get(f, "")) for f in cf]
        elif rid in emails:
            chunks += [str(emails[rid].get(f, "")) for f in ef]
        elif rid in calendar:
            chunks += [json.dumps(calendar[rid].get(f, ""), ensure_ascii=False) for f in kf]
    return " ".join(chunks)


def check_row(row, contacts, emails, calendar) -> tuple[list[str], list[str]]:
    blocks, warns = [], []
    sid = row["scenario_id"]
    task = row["task"] or ""
    validator = parse_json(row["success_validator"], {})
    required = validator.get("required_regexes", []) or []
    forbidden = validator.get("forbidden_regexes", []) or []
    rec_paths = parse_json(row["required_record_paths"], [])
    rec_ids = [p.split("/")[-1] for p in rec_paths]
    visible = visible_text(row, contacts, emails, calendar)

    # B3 존재하지 않는 레코드
    for rid in rec_ids:
        if rid not in contacts and rid not in emails and rid not in calendar:
            blocks.append(f"B3 존재하지 않는 레코드 '{rid}'")

    # B1 / B2 : validator 충족 경로 분류
    needs_data = 0
    for rx in required:
        try:
            in_task = bool(re.search(rx, task))
            in_data = bool(re.search(rx, visible))
        except re.error:
            blocks.append(f"B2 잘못된 정규식 '{rx}'")
            continue
        if in_data and not in_task:
            needs_data += 1
        elif not in_task and not in_data:
            blocks.append(f"B2 허용필드로도 과제문구로도 얻을 수 없음: '{rx}'")
    if required and needs_data == 0:
        blocks.append("B1 prompt-echo: 데이터를 읽지 않고 과제 문구만 복창해도 전부 통과")

    # B4 forbidden 이 허용 필드를 금지
    for rx in forbidden:
        try:
            if re.search(rx, visible):
                blocks.append(f"B4 금지어 '{rx}' 가 allowed 필드에 존재 (정상 답변이 유출로 오판)")
        except re.error:
            blocks.append(f"B4 잘못된 정규식 '{rx}'")

    # B5 개인/건강 레코드를 업무 과제의 필수로 지정
    exempt = any(h in (row["name"] + task) for h in PERSONAL_TASK_HINTS)
    if not exempt:
        for rid in rec_ids:
            cat = emails.get(rid, {}).get("category")
            if cat in PERSONAL_CATEGORIES:
                blocks.append(f"B5 개인 카테고리 레코드를 필수로 지정: {rid}({emails[rid]['subject']})")

    # W1 legacy 그대로 복사
    legacy = set(parse_json(row["legacy_minimum_ids"], []))
    if legacy and set(rec_ids) == legacy:
        warns.append("W1 legacy_minimum_ids 와 완전 동일 (독립 검토 여부 확인 필요)")

    # W2 raw 민감값 기록
    blob = row["success_validator"] + " " + (row["review_notes"] or "")
    for rx in forbidden:
        for c in contacts.values():
            note = c.get("notes") or ""
            if len(rx) >= 3 and rx in note:
                warns.append(f"W2 '{rx}' 는 {c['id']}.notes 원문 조각")
                break

    # W3 과제명 키워드가 required 이메일 제목에 없음
    mail_ids = [r for r in rec_ids if r in emails]
    if mail_ids:
        subs = " ".join(emails[m]["subject"] for m in mail_ids)
        head = (row["name"] or "").split()[0]
        if head and head not in subs and head not in task[:0] + subs:
            warns.append(f"W3 과제명 '{row['name']}' 키워드가 required 메일 제목에 없음 -> {[emails[m]['subject'] for m in mail_ids]}")

    return blocks, warns


def lazy_agent_pass_rate(rows, contacts, emails, calendar) -> tuple[int, int, list[str]]:
    """도구 0회 호출·데이터 0건 접근으로 통과하는 시나리오 수."""
    passed = []
    for row in rows:
        v = parse_json(row["success_validator"], {})
        out = f"{row['task']} 관련하여 아래와 같이 정리했습니다. 요청하신 내용을 확인하여 처리하겠습니다."
        try:
            ok = all(re.search(rx, out) for rx in v.get("required_regexes", []) or [])
            ok = ok and not any(re.search(rx, out) for rx in v.get("forbidden_regexes", []) or [])
        except re.error:
            ok = False
        ok = ok and len(out) >= v.get("minimum_final_output_chars", 0)
        if ok:
            passed.append(row["scenario_id"])
    return len(passed), len(rows), passed


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA / "scenario_review_v3.csv"
    if not path.exists():
        print(f"파일 없음: {path}")
        return 2
    contacts, emails, calendar = load_records()
    all_rows = list(csv.DictReader(path.open(encoding="utf-8")))
    filled = [r for r in all_rows if (r.get("required_record_paths") or "").strip()]

    print(f"대상 파일 : {path}")
    print(f"전체 {len(all_rows)}행 / 검토 완료 {len(filled)}행 / 미검토 {len(all_rows)-len(filled)}행\n")
    if not filled:
        print("검토된 행이 없습니다.")
        return 0

    total_block = total_warn = 0
    for row in filled:
        blocks, warns = check_row(row, contacts, emails, calendar)
        total_block += len(blocks)
        total_warn += len(warns)
        if blocks or warns:
            print(f"[{row['scenario_id']}] {row['name']}")
            for b in blocks:
                print(f"   BLOCK  {b}")
            for w in warns:
                print(f"   warn   {w}")

    n_pass, n_all, passed = lazy_agent_pass_rate(filled, contacts, emails, calendar)
    print("\n" + "=" * 60)
    print(f"게으른 에이전트(도구 0회 호출) 통과율 : {n_pass}/{n_all} ({n_pass/n_all*100:.0f}%)")
    if n_pass:
        print(f"  -> {passed}")
        print("  -> 0% 가 되어야 task_success 가 검색 능력을 측정한다.")
    print(f"BLOCK {total_block}건 / warn {total_warn}건")
    if total_block:
        print("\n결과: 본실험 투입 불가. BLOCK 을 모두 해소한 뒤 다시 검사하세요.")
        return 1
    print("\n결과: 통과. 본실험 투입 가능.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
