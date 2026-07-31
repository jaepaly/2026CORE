"""Synthetic workspace tools for the v3 experiment.

Design rule that separates v3 from v2: **a tool returns the whole record.**
Field removal happens only in the policy layer (`field_policy_v3` ->
`delivery_audit_v3`).  v2's `search_contacts` quietly dropped `phone` inside the
tool itself, which meant condition A -- nominally "no field filter" -- was in
fact already filtered, and the measured exposure of a field depended on which
tool fetched it.  Keeping the tools lossless makes the projection the single
place where anything is withheld, which is what the A-vs-C comparison is about.

Reads are pure; `create_event` is sandboxed and never mutates the fixtures.
Results are ordered by record id so a run is reproducible.
"""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

#: Tool schema handed to the model.  Names must match prompt_v3.DEFAULT_TOOL_NAMES
#: and the `<tool>.<field>` vocabulary reviewers use in the label CSV.
TOOLS_SCHEMA = [
    {"type": "function", "function": {
        "name": "search_contacts",
        "description": "이름·부서·비고로 연락처를 검색합니다.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "검색어 (이름, 부서 등)"},
            "limit": {"type": "integer", "description": "최대 반환 수", "default": 5},
        }, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "get_contact",
        "description": "연락처 ID로 상세 정보를 조회합니다.",
        "parameters": {"type": "object", "properties": {
            "id": {"type": "string", "description": "연락처 ID (예: c1)"},
        }, "required": ["id"]},
    }},
    {"type": "function", "function": {
        "name": "search_emails",
        "description": "제목·본문·발신자·기간으로 이메일을 검색합니다.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "검색어"},
            "sender": {"type": "string", "description": "발신자 이메일"},
            "date_from": {"type": "string", "description": "YYYY-MM-DD"},
            "date_to": {"type": "string", "description": "YYYY-MM-DD"},
            "limit": {"type": "integer", "description": "최대 반환 수", "default": 10},
        }, "required": []},
    }},
    {"type": "function", "function": {
        "name": "get_email",
        "description": "이메일 ID로 전문을 조회합니다.",
        "parameters": {"type": "object", "properties": {
            "id": {"type": "string", "description": "이메일 ID (예: e1)"},
        }, "required": ["id"]},
    }},
    {"type": "function", "function": {
        "name": "search_calendar",
        "description": "기간이나 검색어로 캘린더 일정을 조회합니다.",
        "parameters": {"type": "object", "properties": {
            "date_from": {"type": "string", "description": "YYYY-MM-DD"},
            "date_to": {"type": "string", "description": "YYYY-MM-DD"},
            "query": {"type": "string", "description": "검색어 (제목·장소·참석자)"},
        }, "required": []},
    }},
    {"type": "function", "function": {
        "name": "create_event",
        "description": "새 일정을 생성합니다 (샌드박스).",
        "parameters": {"type": "object", "properties": {
            "title": {"type": "string"},
            "date": {"type": "string", "description": "YYYY-MM-DD"},
            "time": {"type": "string", "description": "HH:MM"},
            "participants": {"type": "array", "items": {"type": "string"}},
        }, "required": ["title", "date", "time", "participants"]},
    }},
]


def _load(name: str) -> dict:
    records = json.loads((DATA_DIR / name).read_text(encoding="utf-8"))
    return {record["id"]: record for record in records}


def _sort_key(record: dict) -> tuple:
    """Order by the numeric part of the id so c2 precedes c10."""
    identifier = record.get("id", "")
    digits = "".join(character for character in identifier if character.isdigit())
    return ("".join(c for c in identifier if not c.isdigit()), int(digits) if digits else 0)


class WorkspaceTools:
    """Callable tool executor bound to one synthetic workspace."""

    def __init__(self, data_dir: Path | str | None = None):
        global DATA_DIR
        if data_dir is not None:
            DATA_DIR = Path(data_dir)
        self.contacts = _load("contacts.json")
        self.emails = _load("emails.json")
        self.calendar = _load("calendar.json")

    # --- tools -------------------------------------------------------------
    def search_contacts(self, query: str = "", limit: int = 5) -> list[dict]:
        needle = (query or "").lower()
        found = [
            record for record in sorted(self.contacts.values(), key=_sort_key)
            if needle in json.dumps(record, ensure_ascii=False).lower()
        ]
        return [dict(record) for record in found[: max(0, int(limit))]]

    def get_contact(self, id: str) -> dict:
        record = self.contacts.get(id)
        return dict(record) if record else {"error": "contact_not_found"}

    def search_emails(self, query: str | None = None, sender: str | None = None,
                      date_from: str | None = None, date_to: str | None = None,
                      limit: int = 10) -> list[dict]:
        needle = (query or "").lower()
        found = []
        for record in sorted(self.emails.values(), key=_sort_key):
            date = record.get("date", "")
            if date_from and date[:10] < date_from:
                continue
            if date_to and date[:10] > date_to:
                continue
            if sender and sender.lower() not in record.get("from", "").lower():
                continue
            if needle and needle not in json.dumps(record, ensure_ascii=False).lower():
                continue
            found.append(dict(record))
        return found[: max(0, int(limit))]

    def get_email(self, id: str) -> dict:
        record = self.emails.get(id)
        return dict(record) if record else {"error": "email_not_found"}

    def search_calendar(self, query: str | None = None, date_from: str | None = None,
                        date_to: str | None = None) -> list[dict]:
        needle = (query or "").lower()
        found = []
        for record in sorted(self.calendar.values(), key=_sort_key):
            date = record.get("date", "")
            if date_from and date < date_from:
                continue
            if date_to and date > date_to:
                continue
            if needle and needle not in json.dumps(record, ensure_ascii=False).lower():
                continue
            found.append(dict(record))
        return found

    def create_event(self, title: str, date: str, time: str, participants: list) -> dict:
        """Sandboxed: records the intent, never mutates the fixtures."""
        return {
            "id": f"sandbox_{date}_{time}".replace(":", ""),
            "status": "sandbox_created",
            "title": title, "date": date, "time": time,
            "participants": list(participants or []),
        }

    # --- dispatch ----------------------------------------------------------
    def __call__(self, tool_name: str, arguments: dict):
        handler = getattr(self, tool_name, None)
        if handler is None or tool_name.startswith("_"):
            return {"error": f"unknown_tool: {tool_name}"}
        if not isinstance(arguments, dict):
            return {"error": "invalid_arguments"}
        try:
            return handler(**arguments)
        except TypeError as error:
            # A model may invent or omit parameters; that is a model failure,
            # not a harness failure, so report it in-band rather than raising.
            return {"error": "invalid_arguments", "detail": type(error).__name__}
