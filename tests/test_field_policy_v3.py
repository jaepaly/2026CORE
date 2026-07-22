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

    def test_projection_condition_denies_tool_without_reviewed_projection(self):
        decision = resolve_delivery_policy(
            condition="C",
            tool_name="get_email",
            projection_by_tool={"get_contact": ["id", "name"]},
        )

        self.assertEqual("denied", decision["decision"])
        self.assertEqual("missing_task_aware_projection", decision["denial_reason"])


if __name__ == "__main__":
    unittest.main()
