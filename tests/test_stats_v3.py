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

        self.assertEqual(3, result["paired_valid_run_count"])
        self.assertEqual(1, result["a_only_success_count"])
        self.assertEqual(1, result["c_only_success_count"])
        self.assertEqual(0.0, result["paired_risk_difference_a_minus_c"])
        self.assertEqual(1.0, result["mcnemar_exact_two_sided_p"])
        self.assertEqual(1, result["excluded_unpaired_or_invalid_count"])

    def test_paired_bootstrap_reports_difference_and_deterministic_confidence_interval(self):
        result = paired_bootstrap_mean_difference([(3, 1), (4, 2)], iterations=200, seed=11)

        self.assertEqual(2.0, result["mean_difference_a_minus_c"])
        self.assertEqual([2.0, 2.0], result["bootstrap_95_ci"])
        self.assertEqual(200, result["bootstrap_iterations"])


if __name__ == "__main__":
    unittest.main()
