import unittest

from verify_rerun_v3 import compare


def event(tool, args_sha, delivered, removed=(), records=("c1",)):
    return {
        "tool_name": tool,
        "requested_args_sha256": args_sha,
        "delivered_field_paths": list(delivered),
        "removed_field_paths": list(removed),
        "delivered_record_ids": list(records),
    }


def run(run_id, condition, events, *, excess=0, output_sha="s", task=False, safe=False):
    return {
        "run_id": run_id, "condition": condition, "delivery_events": events,
        "excess_sensitive_field_count": excess, "final_output_sha256": output_sha,
        "task_success": task, "safe_completion": safe,
    }


def batch(events_by_run, **kwargs):
    return [run(rid, cond, evs, **kwargs.get(rid, {}))
            for rid, (cond, evs) in events_by_run.items()]


class OrderInvarianceTest(unittest.TestCase):
    """The gate's real question: did the fix change anything beyond key order?"""

    def test_same_tool_path_with_same_field_sets_passes(self):
        # Same call, subfields listed in a different order -- exactly what the
        # determinism fix normalised.  Sets ignore order, so this must pass.
        before = [run("r1", "A", [event("search_contacts", "h1", ["[].id", "[].name"])])]
        after = [run("r1", "A", [event("search_contacts", "h1", ["[].name", "[].id"])])]

        report = compare(before, after)

        self.assertTrue(report["order_invariance"]["passed"])
        self.assertEqual(0, report["order_invariance"]["field_set_violations"])

    def test_same_tool_path_with_different_fields_fails(self):
        before = [run("r1", "A", [event("search_contacts", "h1", ["[].id", "[].name"])])]
        after = [run("r1", "A", [event("search_contacts", "h1", ["[].id", "[].name", "[].phone"])])]

        report = compare(before, after)

        self.assertFalse(report["order_invariance"]["passed"])
        self.assertEqual(["r1"], report["order_invariance"]["violation_examples"])

    def test_diverged_tool_path_is_not_judged(self):
        """A model that called different tools is non-determinism, not a bug.

        This is the case the previous gate reported as failure: delivery moves
        because different records were fetched, which the fix cannot cause.
        """
        before = [run("r1", "A", [event("get_email", "h1", ["body"])], excess=1)]
        after = [run("r1", "A", [event("search_emails", "h2", ["[].subject"])], excess=0)]

        report = compare(before, after)

        self.assertTrue(report["order_invariance"]["passed"])
        self.assertEqual(1, report["behavioural_divergence"]["diverged_tool_path_runs"])
        # The mean moved by a full point and the gate still does not judge it.
        self.assertEqual(-1.0, report["delivery"]["A"]["delta"])


class ProjectionContractTest(unittest.TestCase):
    def test_projected_conditions_must_deliver_nothing(self):
        before = [run("r1", "C", [event("search_contacts", "h1", ["[].id"])], excess=0)]
        after = [run("r1", "C", [event("search_contacts", "h1", ["[].id"])], excess=2)]

        report = compare(before, after)

        self.assertFalse(report["projection_contract"]["C"]["held"])

    def test_contract_holds_when_both_are_zero(self):
        before = [run("r1", "C", [event("search_contacts", "h1", ["[].id"])], excess=0)]
        after = [run("r1", "C", [event("search_contacts", "h1", ["[].id"])], excess=0)]

        report = compare(before, after)

        self.assertTrue(report["projection_contract"]["C"]["held"])
        self.assertTrue(report["projection_contract"]["D"]["held"])  # absent -> 0.0 both sides


class ComparabilityTest(unittest.TestCase):
    def test_almost_no_comparable_runs_cannot_be_judged(self):
        before = [run(f"r{i}", "A", [event("get_email", f"h{i}", ["body"])]) for i in range(10)]
        after = [run(f"r{i}", "A", [event("search_emails", f"x{i}", ["[].subject"])])
                 for i in range(10)]

        report = compare(before, after)

        self.assertEqual(0, report["order_invariance"]["same_tool_path_runs"])
        self.assertFalse(report["order_invariance"]["enough_to_judge"])

    def test_output_hash_change_is_counted_not_judged(self):
        before = [run("r1", "A", [event("search_contacts", "h1", ["[].id"])], output_sha="a")]
        after = [run("r1", "A", [event("search_contacts", "h1", ["[].id"])], output_sha="b")]

        report = compare(before, after)

        self.assertEqual(1, report["behavioural_divergence"]["output_hash_changed"])
        self.assertTrue(report["order_invariance"]["passed"])


if __name__ == "__main__":
    unittest.main()
