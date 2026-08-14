"""Static checks on an authored field-access policy, before it is enforced.

The policy-authoring experiment found that models write policies no human wrote
(exact match 0/172), but that the failures split by cause.  Some need a person --
whether an email body is sensitive for this task cannot be decided without
reading it.  Others do not: naming a field that does not exist, or granting
detail fields the agent has no way to reach, are properties of the policy alone
and can be decided by looking at the tool graph.

This module is that second half.  It takes a policy and a description of the
tools it applies to, and reports what is wrong without consulting any reviewer
label, any model, or any run.  It is the "스키마 검증" step in the pipeline the
results section proposes: model drafts, this rejects the mechanically broken
drafts, and a person spends their attention on what is left.

Two diagnostic severities, because the two mean different things:

``error``
    The policy cannot work.  ``P1`` names a field the tools cannot return;
    ``P2`` grants a detail tool no reachable identifier, so the agent can look
    up nothing.  A policy with errors will fail regardless of judgement.
``warning``
    The policy will run but probably not as intended.  ``P3`` grants a tool's
    fields without its identifier, so results cannot be referenced or chained
    later; ``P4`` grants nothing at all.

Nothing here is specific to this study's workspace.  Callers describe their own
tools through :class:`ToolGraph`, so the same check applies to any agent whose
tools return records.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Identifier field name.  Kept as a constant rather than inlined because a
#: caller whose records key on something else needs one place to change.
IDENTIFIER = "id"


@dataclass(frozen=True)
class Tool:
    """One tool a policy can grant fields on.

    ``discovery_tool`` names the tool that produces identifiers for this one.
    A detail tool -- one that takes an id and returns a single record -- is
    useless unless some discovery tool hands the agent that id first, and that
    dependency is what :func:`lint_policy` checks.  Discovery tools leave it
    None: they are reached from the task text, not from another call.
    """

    name: str
    fields: frozenset[str]
    discovery_tool: str | None = None
    writes: bool = False


@dataclass
class ToolGraph:
    tools: dict[str, Tool] = field(default_factory=dict)

    def add(self, name: str, fields, *, discovery_tool: str | None = None,
            writes: bool = False) -> "ToolGraph":
        self.tools[name] = Tool(name, frozenset(fields), discovery_tool, writes)
        return self

    def field_paths(self) -> set[str]:
        return {f"{t.name}.{f}" for t in self.tools.values() for f in t.fields}


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: str  # "error" | "warning"
    tool: str | None
    message: str

    def __str__(self) -> str:
        where = f"{self.tool}: " if self.tool else ""
        return f"[{self.code}] {where}{self.message}"


def _by_tool(policy) -> dict[str, set[str]]:
    """Accept either {tool: [fields]} or a flat list of ``tool.field`` paths."""
    grouped: dict[str, set[str]] = {}
    if isinstance(policy, dict):
        for tool, fields in policy.items():
            if isinstance(fields, str):
                fields = [fields]
            grouped.setdefault(tool, set()).update(
                f.split(".", 1)[1] if f.startswith(f"{tool}.") else f for f in fields or ())
    else:
        for path in policy or ():
            tool, _, field_name = str(path).partition(".")
            if field_name:
                grouped.setdefault(tool, set()).add(field_name)
    return {tool: fields for tool, fields in grouped.items() if fields}


def lint_policy(policy, graph: ToolGraph) -> list[Diagnostic]:
    """Report what is mechanically wrong with ``policy``. No labels consulted."""
    granted = _by_tool(policy)
    found: list[Diagnostic] = []

    if not granted:
        return [Diagnostic("P4", "warning", None, "정책이 어떤 필드도 허용하지 않습니다")]

    for tool_name in sorted(granted):
        tool = graph.tools.get(tool_name)
        if tool is None:
            found.append(Diagnostic(
                "P1", "error", tool_name, f"존재하지 않는 도구입니다"))
            continue
        unknown = sorted(granted[tool_name] - tool.fields)
        if unknown:
            found.append(Diagnostic(
                "P1", "error", tool_name,
                f"이 도구가 반환할 수 없는 필드: {', '.join(unknown)}"))

    for tool_name in sorted(granted):
        tool = graph.tools.get(tool_name)
        if tool is None or tool.writes:
            continue
        # A detail tool needs an id from somewhere.  Without it the agent holds
        # a permission it can never exercise -- the policy looks generous and
        # delivers nothing.
        if tool.discovery_tool:
            source = granted.get(tool.discovery_tool, set())
            if IDENTIFIER not in source:
                found.append(Diagnostic(
                    "P2", "error", tool_name,
                    f"식별자를 얻을 경로가 없습니다 — "
                    f"{tool.discovery_tool}.{IDENTIFIER} 가 허용되지 않았습니다"))
        elif IDENTIFIER in tool.fields and IDENTIFIER not in granted[tool_name]:
            found.append(Diagnostic(
                "P3", "warning", tool_name,
                f"{IDENTIFIER} 가 없어 조회 결과를 이후 단계에서 참조할 수 없습니다"))

    return found


def has_errors(diagnostics) -> bool:
    return any(d.severity == "error" for d in diagnostics)


def workspace_tool_graph(tools=None) -> ToolGraph:
    """The tool graph for this study's synthetic workspace.

    Built from the fixtures rather than hand-listed so it cannot drift from what
    the tools actually return.
    """
    from policy_authoring_v3 import build_field_vocabulary
    from tools_v3 import WorkspaceTools

    vocabulary = build_field_vocabulary(tools or WorkspaceTools())
    graph = ToolGraph()
    for name, fields in vocabulary.items():
        detail = name.startswith("get_")
        graph.add(
            name, fields,
            discovery_tool=("search_" + name.split("_", 1)[1] + "s") if detail else None,
        )
    graph.add("create_event", (), writes=True)
    return graph
