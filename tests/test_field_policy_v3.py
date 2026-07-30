import unittest

from field_policy_v3 import resolve_delivery_policy


class FieldPolicyV3Tests(unittest.TestCase):
    def test_neutral_condition_does_not_apply_projection(self):
        decision = resolve_delivery_policy(
            condition="A",
            tool_name="get_contact",
            projection_by_tool={"get_contact": ["id", "name"]},
        )

        self.assertEqual("allowed", decision["decision"])
        self.assertIsNone(decision["allowed_field_paths"])

    def test_projection_condition_uses_only_reviewed_tool_fields(self):
        decision = resolve_delivery_policy(
            condition="C",
            tool_name="get_contact",
            projection_by_tool={"get_contact": ["id", "name", "email"]},
        )

        self.assertEqual("allowed", decision["decision"])
        self.assertEqual({"id", "name", "email"}, decision["allowed_field_paths"])

    def test_unreviewed_tool_is_still_callable_but_projected_to_nothing(self):
        """C/D must not deny tools: that would confound fields with capability."""
        decision = resolve_delivery_policy(
            condition="C",
            tool_name="get_email",
            projection_by_tool={"get_contact": ["id", "name"]},
        )

        self.assertEqual("allowed", decision["decision"])
        self.assertEqual(set(), decision["allowed_field_paths"])
        self.assertEqual("unreviewed_tool_defaults_to_empty", decision["projection_source"])

    def test_no_primary_condition_denies_a_tool(self):
        for condition in ("A", "B", "C", "D"):
            with self.subTest(condition=condition):
                decision = resolve_delivery_policy(
                    condition=condition,
                    tool_name="create_event",
                    projection_by_tool={},
                )
                self.assertEqual("allowed", decision["decision"])

    def test_capability_denial_is_a_separate_opt_in_axis_with_its_own_reason(self):
        decision = resolve_delivery_policy(
            condition="C",
            tool_name="create_event",
            projection_by_tool={"create_event": ["status"]},
            denied_tools={"create_event"},
        )

        self.assertEqual("denied", decision["decision"])
        self.assertEqual("capability_denied", decision["denial_reason"])


if __name__ == "__main__":
    unittest.main()
