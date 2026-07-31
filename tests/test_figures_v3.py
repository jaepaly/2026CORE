import json
import tempfile
import unittest
from pathlib import Path

from figures_v3 import main

ROOT = Path(__file__).resolve().parents[1]
REVIEW_CSV = ROOT / "data" / "scenario_review_v3.csv"


def run(scenario, condition, *, model="m1", safe=True, sensitive=0, status="completed",
        validation="valid"):
    return {
        "model": model, "scenario": scenario, "condition": condition, "seed": 0,
        "retry_index": 0, "status": status, "validation_status": validation,
        "task_success": True if validation == "valid" else None,
        "safe_completion": safe if validation == "valid" else None,
        "excess_sensitive_field_count": sensitive,
        "executed_tools": ["get_contact"],
        "delivery_events": [{
            "policy_decision": "allowed",
            "delivered_field_paths": ["id"],
            "removed_field_paths": [],
            "delivered_sensitive_field_paths": ["phone"] * sensitive,
            "delivered_record_ids": ["c1"],
        }],
    }


def write_runs(directory: Path, rows):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "runs.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


class FigureGenerationTests(unittest.TestCase):
    def test_single_model_produces_the_core_figures(self):
        rows = []
        for index in range(1, 5):
            rows.append(run(f"v3_s{index}", "A", sensitive=2, safe=False))
            rows.append(run(f"v3_s{index}", "C", sensitive=0, safe=True))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_runs(root / "exp", rows)
            out = root / "figs"

            code = main(["--experiment-dir", str(root / "exp"), "--out-dir", str(out),
                         "--review-csv", str(REVIEW_CSV)])
            made = {p.name for p in out.glob("*.png")}

        self.assertEqual(0, code)
        self.assertIn("fig_v3_layers.png", made)
        self.assertIn("fig_v3_primary.png", made)
        self.assertIn("fig_v3_run_health.png", made)
        # One model gives nothing to compare across models.
        self.assertNotIn("fig_v3_by_model.png", made)

    def test_several_models_add_the_cross_model_figure(self):
        rows = []
        for model in ("m1", "m2"):
            for index in range(1, 4):
                rows.append(run(f"v3_s{index}", "A", model=model, sensitive=2, safe=False))
                rows.append(run(f"v3_s{index}", "C", model=model, safe=True))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_runs(root / "exp", rows)
            out = root / "figs"

            main(["--experiment-dir", str(root / "exp"), "--out-dir", str(out),
                  "--review-csv", str(REVIEW_CSV)])
            made = {p.name for p in out.glob("*.png")}

        self.assertIn("fig_v3_by_model.png", made)

    def test_runs_without_a_usable_pair_still_render(self):
        """Early in a batch there may be no complete A/C pair yet."""
        rows = [run("v3_s1", "A", sensitive=1, safe=False),
                run("v3_s2", "B", sensitive=1, safe=False)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_runs(root / "exp", rows)
            out = root / "figs"

            code = main(["--experiment-dir", str(root / "exp"), "--out-dir", str(out),
                         "--review-csv", str(REVIEW_CSV)])

        self.assertEqual(0, code)

    def test_technical_failures_appear_in_the_health_figure_inputs(self):
        rows = [run("v3_s1", "A", validation="technical_failure", status="technical_failure"),
                run("v3_s1", "C", safe=True)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_runs(root / "exp", rows)
            out = root / "figs"

            code = main(["--experiment-dir", str(root / "exp"), "--out-dir", str(out),
                         "--review-csv", str(REVIEW_CSV)])

        self.assertEqual(0, code)


if __name__ == "__main__":
    unittest.main()
