"""Validation for the pre-registered v3 controlled-disclosure protocol."""

import hashlib
import json
from pathlib import Path


def load_protocol(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_protocol(protocol: dict) -> dict:
    conditions = protocol.get("conditions", {})
    if set(conditions) != {"A", "B", "C", "D"}:
        raise ValueError("conditions must contain exactly A, B, C, D")
    for condition in conditions.values():
        if condition.get("tool_denial") != "none":
            raise ValueError("tool denial is not allowed in the primary factorial conditions")
    return protocol


def _validate_prompt_axis(protocol: dict, prompt_sha256_by_condition: dict[str, str]) -> None:
    """Fail if the declared minimum_access_prompt factor is not actually applied.

    The protocol declares which conditions carry the minimum-access prompt.  If
    two conditions differ on that flag but share a prompt hash, the factor exists
    only on paper and the 2x2 has silently collapsed to a 1x2.
    """
    conditions = protocol["conditions"]
    missing = sorted(set(conditions) - set(prompt_sha256_by_condition))
    if missing:
        raise ValueError(f"missing prompt hash for conditions: {', '.join(missing)}")
    for name, settings in conditions.items():
        for other_name, other_settings in conditions.items():
            same_hash = prompt_sha256_by_condition[name] == prompt_sha256_by_condition[other_name]
            same_flag = settings["minimum_access_prompt"] == other_settings["minimum_access_prompt"]
            if same_flag and not same_hash:
                raise ValueError(
                    f"conditions {name}/{other_name} share minimum_access_prompt but differ in prompt"
                )
            if not same_flag and same_hash:
                raise ValueError(
                    f"conditions {name}/{other_name} differ in minimum_access_prompt "
                    "but share an identical prompt: the prompt factor is not implemented"
                )


def _file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def initialize_manifest(
    *,
    experiment_dir: str | Path,
    protocol_path: str | Path,
    scenario_path: str | Path,
    git_commit: str,
    models: list[dict],
    planned_runs: list[dict],
    prompt_sha256_by_condition: dict[str, str] | None = None,
) -> dict:
    protocol = validate_protocol(load_protocol(protocol_path))
    for model in models:
        if not isinstance(model, dict) or not model.get("name") or not model.get("digest"):
            raise ValueError("model digest is required for every planned model")
    run_keys = [
        (run.get("model"), run.get("scenario"), run.get("condition"), run.get("seed"), run.get("retry_index"))
        for run in planned_runs
    ]
    if len(run_keys) != len(set(run_keys)):
        raise ValueError("duplicate planned run key")
    if prompt_sha256_by_condition:
        _validate_prompt_axis(protocol, prompt_sha256_by_condition)
    manifest = {
        "schema_version": "v3.0",
        "git_commit": git_commit,
        "protocol_sha256": _file_sha256(protocol_path),
        "scenario_sha256": _file_sha256(scenario_path),
        "protocol": protocol,
        "prompt_sha256_by_condition": prompt_sha256_by_condition or {},
        "models": models,
        "planned_runs": planned_runs,
    }
    experiment_dir = Path(experiment_dir)
    experiment_dir.mkdir(parents=True, exist_ok=True)
    (experiment_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def validate_manifest_integrity(
    manifest: dict,
    *,
    protocol_path: str | Path,
    scenario_path: str | Path,
    execution_started: bool,
) -> None:
    if not execution_started:
        return
    if manifest.get("protocol_sha256") != _file_sha256(protocol_path):
        raise ValueError("protocol hash changed after execution started")
    if manifest.get("scenario_sha256") != _file_sha256(scenario_path):
        raise ValueError("scenario hash changed after execution started")
