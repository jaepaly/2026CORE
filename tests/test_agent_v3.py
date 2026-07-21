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

    def test_projection_without_reviewed_tool_fields_returns_a_denial_event(self):
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

        self.assertEqual({"error": "policy_denied", "reason": "missing_task_aware_projection"}, delivered)
        self.assertEqual("denied", event["policy_decision"])
        self.assertEqual("missing_task_aware_projection", event["denial_reason"])
        self.assertEqual([], event["delivered_field_paths"])

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
