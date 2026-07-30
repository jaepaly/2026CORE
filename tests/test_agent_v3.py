import unittest

from agent_v3 import apply_policy_to_tool_result


class AgentV3BoundaryTests(unittest.TestCase):
    def test_neutral_condition_delivers_full_tool_result_and_records_sensitive_fields(self):
        raw_result = {"id": "c1", "name": "김민수", "phone": "010-1234-5678"}

        delivered, event = apply_policy_to_tool_result(
            condition="A",
            projection_by_tool={"get_contact": ["id", "name"]},
            sensitive_field_paths={"phone"},
            raw_result=raw_result,
            run_id="run-a",
            model="local-model",
            scenario="v3_s1",
            seed=0,
            turn=1,
            tool_name="get_contact",
            requested_args={"id": "c1"},
        )

        self.assertEqual(raw_result, delivered)
        self.assertEqual(["phone"], event["delivered_sensitive_field_paths"])
        self.assertEqual("allowed", event["policy_decision"])

    def test_unreviewed_tool_delivers_an_empty_projection_not_a_denial(self):
        """The tool still answers; only its fields are removed (no capability change)."""
        delivered, event = apply_policy_to_tool_result(
            condition="C",
            projection_by_tool={"get_contact": ["id", "name"]},
            sensitive_field_paths={"body"},
            raw_result={"id": "e1", "body": "비밀 본문"},
            run_id="run-c",
            model="local-model",
            scenario="v3_s1",
            seed=0,
            turn=1,
            tool_name="get_email",
            requested_args={"id": "e1"},
        )

        self.assertEqual({}, delivered)
        self.assertEqual("allowed", event["policy_decision"])
        self.assertEqual("unreviewed_tool_defaults_to_empty", event["projection_source"])
        self.assertEqual([], event["delivered_field_paths"])
        self.assertEqual([], event["delivered_sensitive_field_paths"])
        self.assertEqual(["body", "id"], event["removed_field_paths"])
        self.assertNotIn("비밀 본문", str(event))

    def test_opt_in_capability_denial_is_recorded_with_its_own_reason(self):
        delivered, event = apply_policy_to_tool_result(
            condition="C",
            projection_by_tool={"create_event": ["status"]},
            sensitive_field_paths=set(),
            raw_result={"status": "ok"},
            run_id="run-cap",
            model="local-model",
            scenario="v3_s1",
            seed=0,
            turn=1,
            tool_name="create_event",
            requested_args={},
            denied_tools={"create_event"},
        )

        self.assertEqual({"error": "policy_denied", "reason": "capability_denied"}, delivered)
        self.assertEqual("denied", event["policy_decision"])
        self.assertEqual("capability_denied", event["denial_reason"])

    def test_neutral_condition_preserves_list_results(self):
        raw_result = [
            {"id": "e1", "subject": "일정", "body": "비밀 본문"},
            {"id": "e2", "subject": "검토", "body": "다른 본문"},
        ]

        delivered, event = apply_policy_to_tool_result(
            condition="A",
            projection_by_tool={},
            sensitive_field_paths={"body"},
            raw_result=raw_result,
            run_id="run-list",
            model="local-model",
            scenario="v3_s4",
            seed=0,
            turn=1,
            tool_name="search_emails",
            requested_args={"query": ""},
        )

        self.assertEqual(raw_result, delivered)
        self.assertEqual(["[].body"], event["delivered_sensitive_field_paths"])


if __name__ == "__main__":
    unittest.main()
