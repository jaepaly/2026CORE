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
    manifest = {
        "schema_version": "v3.0",
        "git_commit": git_commit,
        "protocol_sha256": _file_sha256(protocol_path),
        "scenario_sha256": _file_sha256(scenario_path),
        "protocol": protocol,
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
