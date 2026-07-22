import json
import tempfile
import unittest
from pathlib import Path

from protocol_v3 import (
    initialize_manifest,
    load_protocol,
    validate_manifest_integrity,
    validate_protocol,
)


ROOT = Path(__file__).resolve().parents[1]


class ProtocolV3Tests(unittest.TestCase):
    def test_committed_protocol_defines_unconfounded_primary_factorial_conditions(self):
        protocol = load_protocol(ROOT / "protocols" / "v3_protocol.json")

        validated = validate_protocol(protocol)

        self.assertEqual(["A", "C"], validated["primary_comparison"])
        self.assertEqual("safe_completion", validated["primary_endpoint"])
        for condition in ("A", "B", "C", "D"):
            self.assertEqual("none", validated["conditions"][condition]["tool_denial"])
        self.assertEqual("none", validated["conditions"]["A"]["field_projection"])
        self.assertEqual("task_aware", validated["conditions"]["C"]["field_projection"])

    def test_rejects_tool_denial_in_a_primary_factorial_condition(self):
        protocol = load_protocol(ROOT / "protocols" / "v3_protocol.json")
        protocol["conditions"]["C"]["tool_denial"] = "create_event"

        with self.assertRaisesRegex(ValueError, "tool denial"):
            validate_protocol(protocol)

    def test_rejects_unknown_factorial_condition(self):
        protocol = load_protocol(ROOT / "protocols" / "v3_protocol.json")
        protocol["conditions"]["E"] = {
            "minimum_access_prompt": False,
            "field_projection": "none",
            "tool_denial": "none",
        }

        with self.assertRaisesRegex(ValueError, "exactly A, B, C, D"):
            validate_protocol(protocol)

    def test_initializes_manifest_with_hashed_protocol_scenario_and_planned_runs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            experiment_dir = Path(temporary_directory) / "experiment"
            scenario_path = Path(temporary_directory) / "scenarios.json"
            scenario_path.write_text(json.dumps({"scenarios": []}), encoding="utf-8")

            manifest = initialize_manifest(
                experiment_dir=experiment_dir,
                protocol_path=ROOT / "protocols" / "v3_protocol.json",
                scenario_path=scenario_path,
                git_commit="abc123",
                models=[{"name": "qwen3:8b", "digest": "sha256:model"}],
                planned_runs=[{
                    "model": "qwen3:8b",
                    "scenario": "v3_s01",
                    "condition": "A",
                    "seed": 0,
                    "retry_index": 0,
                }],
            )

            self.assertEqual("abc123", manifest["git_commit"])
            self.assertEqual(64, len(manifest["protocol_sha256"]))
            self.assertEqual(64, len(manifest["scenario_sha256"]))
            self.assertEqual(1, len(manifest["planned_runs"]))
            self.assertEqual(manifest, load_protocol(experiment_dir / "manifest.json"))

    def test_manifest_rejects_model_without_digest(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            scenario_path = Path(temporary_directory) / "scenarios.json"
            scenario_path.write_text(json.dumps({"scenarios": []}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "model digest"):
                initialize_manifest(
                    experiment_dir=Path(temporary_directory) / "experiment",
                    protocol_path=ROOT / "protocols" / "v3_protocol.json",
                    scenario_path=scenario_path,
                    git_commit="abc123",
                    models=[{"name": "qwen3:8b"}],
                    planned_runs=[],
                )

    def test_manifest_rejects_duplicate_planned_run_key(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            scenario_path = Path(temporary_directory) / "scenarios.json"
            scenario_path.write_text(json.dumps({"scenarios": []}), encoding="utf-8")
            run = {
                "model": "qwen3:8b",
                "scenario": "v3_s01",
                "condition": "A",
                "seed": 0,
                "retry_index": 0,
            }

            with self.assertRaisesRegex(ValueError, "duplicate planned run"):
                initialize_manifest(
                    experiment_dir=Path(temporary_directory) / "experiment",
                    protocol_path=ROOT / "protocols" / "v3_protocol.json",
                    scenario_path=scenario_path,
                    git_commit="abc123",
                    models=[{"name": "qwen3:8b", "digest": "sha256:model"}],
                    planned_runs=[run, run.copy()],
                )

    def test_manifest_integrity_rejects_protocol_change_after_execution_starts(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            protocol_path = root / "protocol.json"
            protocol_path.write_text(
                (ROOT / "protocols" / "v3_protocol.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            scenario_path = root / "scenarios.json"
            scenario_path.write_text(json.dumps({"scenarios": []}), encoding="utf-8")
            manifest = initialize_manifest(
                experiment_dir=root / "experiment",
                protocol_path=protocol_path,
                scenario_path=scenario_path,
                git_commit="abc123",
                models=[{"name": "qwen3:8b", "digest": "sha256:model"}],
                planned_runs=[],
            )
            protocol_path.write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "protocol hash"):
                validate_manifest_integrity(
                    manifest,
                    protocol_path=protocol_path,
                    scenario_path=scenario_path,
                    execution_started=True,
                )


if __name__ == "__main__":

    unittest.main()
