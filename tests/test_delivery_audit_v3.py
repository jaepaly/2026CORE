import json
import unittest

from delivery_audit_v3 import audit_denial, project_and_audit


class DeliveryAuditV3Tests(unittest.TestCase):
    def test_projection_delivers_only_allowed_fields_and_logs_value_free_field_evidence(self):
        raw_result = {
            "id": "c1",
            "name": "김민수",
            "email": "minsu@example.test",
            "phone": "010-1234-5678",
            "notes": "급여 협상 중",
        }

        delivered, event = project_and_audit(
            raw_result=raw_result,
            allowed_field_paths={"id", "name", "email"},
            sensitive_field_paths={"phone", "notes"},
            run_id="run-1",
            model="local-model",
            scenario="v3_s1",
            condition="C",
            seed=0,
            turn=1,
            tool_name="get_contact",
            requested_args={"id": "c1"},
        )

        self.assertEqual(
            {"id": "c1", "name": "김민수", "email": "minsu@example.test"},
            delivered,
        )
        self.assertEqual(["email", "id", "name"], event["delivered_field_paths"])
        self.assertEqual(["notes", "phone"], event["removed_field_paths"])
        self.assertEqual([], event["delivered_sensitive_field_paths"])
        self.assertEqual(["c1"], event["delivered_record_ids"])
        self.assertEqual("allowed", event["policy_decision"])
        self.assertEqual(64, len(event["post_policy_payload_sha256"]))
        serialized = json.dumps(event, ensure_ascii=False)
        self.assertNotIn("010-1234-5678", serialized)
        self.assertNotIn("급여 협상 중", serialized)

    def test_list_projection_uses_schema_paths_and_records_all_delivered_ids(self):
        raw_result = [
            {"id": "e1", "subject": "검토", "body": "비밀 본문"},
            {"id": "e2", "subject": "일정", "body": "다른 비밀"},
        ]

        delivered, event = project_and_audit(
            raw_result=raw_result,
            allowed_field_paths={"id", "subject"},
            sensitive_field_paths={"body"},
            run_id="run-2",
            model="local-model",
            scenario="v3_s2",
            condition="C",
            seed=0,
            turn=1,
            tool_name="search_emails",
            requested_args={"query": "검토"},
        )

        self.assertEqual([{"id": "e1", "subject": "검토"}, {"id": "e2", "subject": "일정"}], delivered)
        self.assertEqual(["[].id", "[].subject"], event["delivered_field_paths"])
        self.assertEqual(["[].body"], event["removed_field_paths"])
        self.assertEqual(["e1", "e2"], event["delivered_record_ids"])
        self.assertEqual([], event["delivered_sensitive_field_paths"])
        self.assertNotIn("비밀 본문", json.dumps(event, ensure_ascii=False))

    def test_denial_event_preserves_reason_without_requested_argument_values(self):
        event = audit_denial(
            run_id="run-3",
            model="local-model",
            scenario="v3_s3",
            condition="E",
            seed=1,
            turn=2,
            tool_name="create_event",
            requested_args={"participants": ["outside@example.test"], "title": "비밀 회의"},
            denial_reason="write_capability_disabled",
        )

        self.assertEqual("denied", event["policy_decision"])
        self.assertEqual("write_capability_disabled", event["denial_reason"])
        self.assertEqual([], event["delivered_field_paths"])
        self.assertEqual([], event["delivered_record_ids"])
        serialized = json.dumps(event, ensure_ascii=False)
        self.assertNotIn("outside@example.test", serialized)
        self.assertNotIn("비밀 회의", serialized)


if __name__ == "__main__":
    unittest.main()
