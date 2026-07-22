"""V3 policy boundary joining reviewed projections and delivery audit events."""

from delivery_audit_v3 import audit_denial, project_and_audit
from field_policy_v3 import resolve_delivery_policy


def apply_policy_to_tool_result(
    *,
    condition: str,
    projection_by_tool: dict[str, list[str]],
    sensitive_field_paths: set[str],
    raw_result: dict,
    run_id: str,
    model: str,
    scenario: str,
    seed: int,
    turn: int,
    tool_name: str,
    requested_args: dict,
) -> tuple[dict, dict]:
    decision = resolve_delivery_policy(
        condition=condition,
        tool_name=tool_name,
        projection_by_tool=projection_by_tool,
    )
    if decision["decision"] == "denied":
        return (
            {"error": "policy_denied", "reason": decision["denial_reason"]},
            audit_denial(
                run_id=run_id,
                model=model,
                scenario=scenario,
                condition=condition,
                seed=seed,
                turn=turn,
                tool_name=tool_name,
                requested_args=requested_args,
                denial_reason=decision["denial_reason"],
            ),
        )

    allowed_fields = decision["allowed_field_paths"]
    if allowed_fields is None:
        if isinstance(raw_result, list):
            allowed_fields = {
                key for item in raw_result if isinstance(item, dict) for key in item
            }
        else:
            allowed_fields = set(raw_result)
    return project_and_audit(
        raw_result=raw_result,
        allowed_field_paths=allowed_fields,
        sensitive_field_paths=sensitive_field_paths,
        run_id=run_id,
        model=model,
        scenario=scenario,
        condition=condition,
        seed=seed,
        turn=turn,
        tool_name=tool_name,
        requested_args=requested_args,
    )
