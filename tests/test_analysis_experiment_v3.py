import json
import tempfile
import unittest
from pathlib import Path

from analysis_experiment_v3 import (
    analyse,
    behaviour_by_condition,
    delivery_by_condition,
    primary_analysis,
)

ROOT = Path(__file__).resolve().parents[1]
REVIEW_CSV = ROOT / "data" / "scenario_review_v3.csv"


def run(scenario, condition, *, model="m1", safe=True, task=True, sensitive=0,
        status="completed", validation="valid", tools=("get_contact",), seed=0):
    events = [{
        "policy_decision": "allowed",
        "delivered_field_paths": ["id", "name"],
        "removed_field_paths": ["phone"] if condition in ("C", "D") else [],
        "delivered_sensitive_field_paths": ["phone"] * sensitive,
        "delivered_record_ids": ["c1"],
    }]
    return {
        "model": model, "scenario": scenario, "condition": condition, "seed": seed,
        "retry_index": 0, "status": status, "validation_status": validation,
        "task_success": task if validation == "valid" else None,
        "safe_completion": safe if validation == "valid" else None,
        "excess_sensitive_field_count": sensitive,
        "delivery_events": events, "executed_tools": list(tools),
    }


class LayerSeparationTests(unittest.TestCase):
    """Delivery and behaviour must never collapse into one number."""

    def setUp(self):
        self.runs = [
            run("v3_s1", "A", sensitive=2, safe=False),
            run("v3_s1", "C", sensitive=0, safe=True),
            run("v3_s2", "A", sensitive=1, safe=False),
            run("v3_s2", "C", sensitive=0, safe=True),
        ]

    def test_delivery_layer_reports_what_the_boundary_handed_over(self):
        delivery = delivery_by_condition(self.runs)

        self.assertEqual(1.5, delivery["A"]["mean_delivered_sensitive_fields"])
        self.assertEqual(0.0, delivery["C"]["mean_delivered_sensitive_fields"])
        self.assertEqual(2, delivery["A"]["runs_with_any_sensitive_delivery"])
        self.assertEqual(0, delivery["C"]["runs_with_any_sensitive_delivery"])

    def test_behaviour_layer_reports_what_the_agent_did(self):
        behaviour = behaviour_by_condition(self.runs)

        self.assertEqual(1.0, behaviour["A"]["task_success_rate"])
        self.assertEqual(0.0, behaviour["A"]["safe_completion_rate"])
        self.assertEqual(1.0, behaviour["C"]["safe_completion_rate"])


class TechnicalFailureTests(unittest.TestCase):
    def test_technical_failures_are_counted_but_left_out_of_endpoint_rates(self):
        runs = [
            run("v3_s1", "A", safe=True),
            run("v3_s2", "A", validation="technical_failure", status="technical_failure"),
        ]

        behaviour = behaviour_by_condition(runs)

        self.assertEqual(2, behaviour["A"]["runs"])
        self.assertEqual(1, behaviour["A"]["technical_failures"])
        self.assertEqual(1, behaviour["A"]["valid_runs"])
        self.assertEqual(1.0, behaviour["A"]["safe_completion_rate"])  # 1/1, not 1/2

    def test_max_turns_is_reported_separately_from_technical_failure(self):
        runs = [run("v3_s1", "A", status="max_turns_reached", task=False, safe=False)]

        behaviour = behaviour_by_condition(runs)

        self.assertEqual(1, behaviour["A"]["max_turns_reached"])
        self.assertEqual(0, behaviour["A"]["technical_failures"])
        self.assertEqual(1, behaviour["A"]["valid_runs"])


class PrimaryAnalysisTests(unittest.TestCase):
    def test_primary_is_restricted_to_a_versus_c(self):
        runs = [run(f"v3_s{i}", c, safe=(c == "C"))
                for i in range(1, 6) for c in ("A", "B", "C", "D")]

        primary = primary_analysis(runs)

        self.assertEqual(["A", "C"], primary["comparison"])
        self.assertEqual(5, primary["paired_valid_unit_count"])
        self.assertEqual(5, primary["c_only_success_count"])

    def test_paired_bootstrap_on_delivered_sensitive_fields(self):
        runs = []
        for i in range(1, 5):
            runs.append(run(f"v3_s{i}", "A", sensitive=2, safe=False))
            runs.append(run(f"v3_s{i}", "C", sensitive=0, safe=True))

        bootstrap = primary_analysis(runs)["delivered_sensitive_fields_a_minus_c"]

        self.assertEqual(2.0, bootstrap["mean_difference_a_minus_c"])
        self.assertEqual([2.0, 2.0], bootstrap["bootstrap_95_ci"])

    def test_repeated_seeds_do_not_inflate_the_unit_count(self):
        runs = []
        for seed in range(4):
            runs.append(run("v3_s1", "A", seed=seed, safe=False))
            runs.append(run("v3_s1", "C", seed=seed, safe=True))

        self.assertEqual(1, primary_analysis(runs)["paired_valid_unit_count"])


class EndToEndTests(unittest.TestCase):
    def test_analyse_reads_runs_jsonl_and_keeps_the_three_layers(self):
        runs = [run("v3_s1", "A", sensitive=2, safe=False), run("v3_s1", "C", safe=True)]
        with tempfile.TemporaryDirectory() as directory:
            experiment_dir = Path(directory)
            (experiment_dir / "runs.jsonl").write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in runs), encoding="utf-8"
            )

            summary = analyse(experiment_dir, REVIEW_CSV)

        self.assertEqual(2, summary["total_runs"])
        self.assertIn("capacity", summary)
        self.assertIn("delivery", summary)
        self.assertIn("behaviour", summary)
        # Capacity comes from labels, so it exists even though only 2 runs were made.
        self.assertEqual(43, summary["capacity"]["scenarios"])

    def test_missing_runs_file_is_an_explicit_error(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SystemExit):
                analyse(Path(directory), REVIEW_CSV)


if __name__ == "__main__":
    unittest.main()
