"""Condition-specific v3 field-delivery policy resolution."""


def resolve_delivery_policy(
    *, condition: str, tool_name: str, projection_by_tool: dict[str, list[str]]
) -> dict:
    if condition.upper() in {"A", "B"}:
        return {"decision": "allowed", "allowed_field_paths": None}

    allowed_fields = projection_by_tool.get(tool_name)
    if allowed_fields is None:
        return {
            "decision": "denied",
            "allowed_field_paths": None,
            "denial_reason": "missing_task_aware_projection",
        }
    return {"decision": "allowed", "allowed_field_paths": set(allowed_fields)}
