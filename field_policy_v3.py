"""Condition-specific v3 field-delivery policy resolution.

The primary factorial (A-D) varies *fields only*.  A tool with no reviewed
projection is still callable under C/D: it returns a result with every field
projected away, not an error.  Delivering ``policy_denied`` there would be
indistinguishable from a capability restriction to the model and would
reintroduce the v2 confound in which field filtering and tool blocking moved
together (`docs/experiment_design_v3.md` lines 22-23).

Genuine capability restriction remains expressible for the separate
capability-restriction experiment via ``denied_tools``.  It emits a distinct
``capability_denied`` reason so it can never be mistaken for a field decision,
and it defaults to empty so no A-D arm ever denies a tool.
"""

from __future__ import annotations

_NEUTRAL_CONDITIONS = frozenset({"A", "B"})


def resolve_delivery_policy(
    *,
    condition: str,
    tool_name: str,
    projection_by_tool: dict[str, list[str]],
    denied_tools: "frozenset[str] | set[str] | None" = None,
) -> dict:
    if denied_tools and tool_name in denied_tools:
        return {
            "decision": "denied",
            "allowed_field_paths": None,
            "denial_reason": "capability_denied",
        }

    if condition.upper() in _NEUTRAL_CONDITIONS:
        return {
            "decision": "allowed",
            "allowed_field_paths": None,
            "projection_source": "none",
        }

    allowed_fields = projection_by_tool.get(tool_name)
    if allowed_fields is None:
        # Callable, but nothing survives projection: a field decision, not a
        # capability decision.
        return {
            "decision": "allowed",
            "allowed_field_paths": set(),
            "projection_source": "unreviewed_tool_defaults_to_empty",
        }
    return {
        "decision": "allowed",
        "allowed_field_paths": set(allowed_fields),
        "projection_source": "reviewed",
    }
