"""Deterministic, value-free v3 endpoint validation."""

import hashlib
import json
import re


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_success_validator(validator: dict) -> dict:
    if not isinstance(validator, dict) or validator.get("schema_version") != "v3.validator.1":
        raise ValueError("success validator must use schema_version v3.validator.1")
    for key in ("required_regexes", "forbidden_regexes"):
        patterns = validator.get(key)
        if not isinstance(patterns, list) or not all(isinstance(pattern, str) and pattern for pattern in patterns):
            raise ValueError(f"{key} must be a list of non-empty regex strings")
        for pattern in patterns:
            re.compile(pattern)
    minimum = validator.get("minimum_final_output_chars")
    if not isinstance(minimum, int) or minimum < 0:
        raise ValueError("minimum_final_output_chars must be a non-negative integer")
    return validator


def evaluate_safe_completion(final_output: str, validator: dict) -> dict:
    validator = validate_success_validator(validator)
    categories = []
    if len(final_output) < validator["minimum_final_output_chars"]:
        categories.append("output_too_short")
    if any(re.search(pattern, final_output) is None for pattern in validator["required_regexes"]):
        categories.append("missing_required_output")
    if any(re.search(pattern, final_output) is not None for pattern in validator["forbidden_regexes"]):
        categories.append("forbidden_output_pattern")
    return {
        "safe_completion": not categories,
        "failure_categories": categories,
        "validator_schema_version": validator["schema_version"],
        "validator_sha256": _canonical_sha256(validator),
    }


def validate_run_outcome(run_status: str, final_output: str, validator: dict) -> dict:
    """Classify endpoint eligibility without returning raw final-output text."""
    result = evaluate_safe_completion(final_output, validator)
    if run_status != "completed":
        result["validation_status"] = "technical_failure"
        result["safe_completion"] = None
        result["failure_categories"] = ["technical_failure"]
    else:
        result["validation_status"] = "valid"
    return result
