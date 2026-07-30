import unittest

from stats_v3 import analyze_primary_safe_completion, paired_bootstrap_mean_difference


class StatsV3Tests(unittest.TestCase):
    def test_primary_analysis_uses_only_valid_paired_a_and_c_outcomes(self):
        events = [
            {"model": "m1", "scenario": "s1", "seed": 0, "retry_index": 0, "condition": "A", "validation_status": "valid", "safe_completion": True},
            {"model": "m1", "scenario": "s1", "seed": 0, "retry_index": 0, "condition": "C", "validation_status": "valid", "safe_completion": True},
            {"model": "m1", "scenario": "s2", "seed": 0, "retry_index": 0, "condition": "A", "validation_status": "valid", "safe_completion": True},
            {"model": "m1", "scenario": "s2", "seed": 0, "retry_index": 0, "condition": "C", "validation_status": "valid", "safe_completion": False},
            {"model": "m1", "scenario": "s3", "seed": 0, "retry_index": 0, "condition": "A", "validation_status": "valid", "safe_completion": False},
            {"model": "m1", "scenario": "s3", "seed": 0, "retry_index": 0, "condition": "C", "validation_status": "valid", "safe_completion": True},
            {"model": "m1", "scenario": "s4", "seed": 0, "retry_index": 0, "condition": "A", "validation_status": "technical_failure", "safe_completion": None},
            {"model": "m1", "scenario": "s4", "seed": 0, "retry_index": 0, "condition": "C", "validation_status": "valid", "safe_completion": True},
        ]

        result = analyze_primary_safe_completion(events)

        self.assertEqual(3, result["paired_valid_unit_count"])
        self.assertEqual(1, result["a_only_success_count"])
        self.assertEqual(1, result["c_only_success_count"])
        self.assertEqual(0.0, result["paired_risk_difference_a_minus_c"])
        self.assertEqual(1.0, result["mcnemar_exact_two_sided_p"])
        self.assertEqual(1, result["excluded_unpaired_or_invalid_count"])


def _event(scenario, condition, safe, *, seed=0, retry_index=0, status="valid", model="m1"):
    return {
        "model": model, "scenario": scenario, "seed": seed, "retry_index": retry_index,
        "condition": condition, "validation_status": status, "safe_completion": safe,
    }


class SeedIndependenceTests(unittest.TestCase):
    """Repeated seeds must not be counted as independent paired observations."""

    def test_repeated_seeds_collapse_to_one_unit(self):
        events = []
        for seed in range(5):
            events.append(_event("s1", "A", True, seed=seed))
            events.append(_event("s1", "C", False, seed=seed))

        result = analyze_primary_safe_completion(events)

        # 5 seeds x 1 scenario is ONE analysis unit, not five.
        self.assertEqual(1, result["paired_valid_unit_count"])
        self.assertEqual(1, result["a_only_success_count"])
        self.assertEqual(1.0, result["mcnemar_exact_two_sided_p"])

    def test_seed_agreement_is_reported_so_duplication_stays_visible(self):
        events = []
        for seed in range(3):
            events.append(_event("s1", "A", True, seed=seed))
            events.append(_event("s1", "C", seed == 0, seed=seed))

        agreement = analyze_primary_safe_completion(events)["seed_agreement"]

        self.assertEqual(2, agreement["condition_groups"])
        self.assertEqual(2, agreement["replicated_groups"])
        self.assertEqual(1, agreement["unanimous_replicated_groups"])  # A unanimous, C split

    def test_seeds_collapse_by_majority_with_ties_resolving_to_false(self):
        events = [
            _event("s1", "A", True, seed=0), _event("s1", "A", False, seed=1),
            _event("s1", "C", True, seed=0), _event("s1", "C", True, seed=1),
        ]

        result = analyze_primary_safe_completion(events)

        # A ties 1-1 -> False; C unanimous True -> C-only success.
        self.assertEqual(1, result["c_only_success_count"])
        self.assertEqual(0, result["a_only_success_count"])


class RetryCollapseTests(unittest.TestCase):
    """retry_index must not fragment a pair; the latest valid attempt wins."""

    def test_retry_repairs_a_pair_broken_by_a_technical_failure(self):
        events = [
            _event("s1", "A", None, retry_index=0, status="technical_failure"),
            _event("s1", "A", True, retry_index=1),
            _event("s1", "C", False, retry_index=0),
        ]

        result = analyze_primary_safe_completion(events)

        self.assertEqual(1, result["paired_valid_unit_count"])
        self.assertEqual(1, result["a_only_success_count"])

    def test_duplicate_run_key_is_rejected(self):
        events = [_event("s1", "A", True), _event("s1", "A", False)]

        with self.assertRaises(ValueError):
            analyze_primary_safe_completion(events)

    def test_paired_bootstrap_reports_difference_and_deterministic_confidence_interval(self):
        result = paired_bootstrap_mean_difference([(3, 1), (4, 2)], iterations=200, seed=11)

        self.assertEqual(2.0, result["mean_difference_a_minus_c"])
        self.assertEqual([2.0, 2.0], result["bootstrap_95_ci"])
        self.assertEqual(200, result["bootstrap_iterations"])


if __name__ == "__main__":
    unittest.main()
