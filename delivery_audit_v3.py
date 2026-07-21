"""Post-policy delivery metadata for v3 tool responses."""

import hashlib
import json


def _sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def project_and_audit(
    *,
    raw_result: dict,
    allowed_field_paths: set[str],
    sensitive_field_paths: set[str],
    run_id: str,
    model: str,
    scenario: str,
    condition: str,
    seed: int,
    turn: int,
    tool_name: str,
    requested_args: dict,
) -> tuple[dict, dict]:
    if isinstance(raw_result, list):
        raw_fields = {key for item in raw_result if isinstance(item, dict) for key in item}
        delivered = [
            {key: item[key] for key in item if key in allowed_field_paths}
            for item in raw_result
            if isinstance(item, dict)
        ]
        delivered_fields = {key for item in delivered for key in item}
        prefix = "[]."
        delivered_record_ids = [item["id"] for item in delivered if "id" in item]
    else:
        raw_fields = set(raw_result)
        delivered = {key: raw_result[key] for key in raw_result if key in allowed_field_paths}
        delivered_fields = set(delivered)
        prefix = ""
        delivered_record_ids = [delivered["id"]] if "id" in delivered else []

    event = {
        "event_type": "post_policy_delivery",
        "run_id": run_id,
        "model": model,
        "scenario": scenario,
        "condition": condition,
        "seed": seed,
        "turn": turn,
        "tool_name": tool_name,
        "requested_arg_keys": sorted(requested_args),
        "requested_args_sha256": _sha256(requested_args),
        "policy_decision": "allowed",
        "raw_field_paths": sorted(f"{prefix}{field}" for field in raw_fields),
        "delivered_field_paths": sorted(f"{prefix}{field}" for field in delivered_fields),
        "removed_field_paths": sorted(f"{prefix}{field}" for field in raw_fields - delivered_fields),
        "delivered_sensitive_field_paths": sorted(
            f"{prefix}{field}" for field in delivered_fields & sensitive_field_paths
        ),
        "delivered_record_ids": delivered_record_ids,
        "post_policy_payload_sha256": _sha256(delivered),
    }
    return delivered, event


def audit_denial(
    *,
    run_id: str,
    model: str,
    scenario: str,
    condition: str,
    seed: int,
    turn: int,
    tool_name: str,
    requested_args: dict,
    denial_reason: str,
) -> dict:
    return {
        "event_type": "post_policy_delivery",
        "run_id": run_id,
        "model": model,
        "scenario": scenario,
        "condition": condition,
        "seed": seed,
        "turn": turn,
        "tool_name": tool_name,
        "requested_arg_keys": sorted(requested_args),
        "requested_args_sha256": _sha256(requested_args),
        "policy_decision": "denied",
        "denial_reason": denial_reason,
        "raw_field_paths": [],
        "delivered_field_paths": [],
        "removed_field_paths": [],
        "delivered_sensitive_field_paths": [],
        "delivered_record_ids": [],
        "post_policy_payload_sha256": None,
    }
