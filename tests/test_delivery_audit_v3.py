import json
import unittest

from delivery_audit_v3 import audit_denial, count_excess_sensitive_fields, project_and_audit


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


CALENDAR_RECORD = {
    "id": "cal2",
    "date": "2025-06-24",
    "day": "화",
    "slots": ["10:00", "11:00"],
    "events": [
        {
            "time": "10:00-11:00",
            "title": "신규 프로젝트 기획 회의",
            "location": "3F 대회의실",
            "participants": ["me", "김민수", "강태오"],
            "type": "내부",
        }
    ],
}


def _audit(allowed, sensitive, raw=None):
    return project_and_audit(
        raw_result=CALENDAR_RECORD if raw is None else raw,
        allowed_field_paths=allowed,
        sensitive_field_paths=sensitive,
        run_id="r", model="m", scenario="v3_s1", condition="C",
        seed=0, turn=1, tool_name="search_calendar", requested_args={},
    )


class NestedFieldTests(unittest.TestCase):
    """Sensitive values nested inside a permitted container must be visible."""

    def test_allowing_a_container_reports_its_nested_sensitive_paths(self):
        delivered, event = _audit({"id", "date", "events"}, {"events[].participants"})

        self.assertIn("김민수", json.dumps(delivered, ensure_ascii=False))
        self.assertEqual(["events[].participants"], event["delivered_sensitive_field_paths"])

    def test_nested_projection_keeps_only_the_named_subfields(self):
        delivered, event = _audit(
            {"id", "date", "events[].time", "events[].location"}, {"events[].participants"}
        )

        self.assertEqual({"time": "10:00-11:00", "location": "3F 대회의실"}, delivered["events"][0])
        self.assertEqual([], event["delivered_sensitive_field_paths"])
        self.assertNotIn("김민수", json.dumps(delivered, ensure_ascii=False))
        self.assertIn("events[].participants", event["removed_field_paths"])

    def test_raw_paths_enumerate_nested_fields(self):
        _, event = _audit({"id"}, set())

        self.assertIn("events[].participants", event["raw_field_paths"])
        self.assertIn("events[].title", event["raw_field_paths"])
        self.assertIn("slots", event["raw_field_paths"])

    def test_unprojected_condition_still_reports_nested_sensitive_delivery(self):
        _, event = _audit(None, {"events[].participants"})

        self.assertEqual(["events[].participants"], event["delivered_sensitive_field_paths"])
        self.assertEqual([], event["removed_field_paths"])

    def test_list_results_prefix_nested_paths(self):
        _, event = _audit({"id"}, {"events[].participants"}, raw=[CALENDAR_RECORD])

        self.assertIn("[].events[].participants", event["raw_field_paths"])
        self.assertIn("[].events[].participants", event["removed_field_paths"])


class ExcessSensitiveCountTests(unittest.TestCase):
    def test_nested_delivery_counts_toward_the_endpoint_privacy_term(self):
        _, leaky = _audit({"id", "events"}, {"events[].participants"})
        _, clean = _audit({"id", "events[].time"}, {"events[].participants"})

        self.assertEqual(1, count_excess_sensitive_fields([leaky]))
        self.assertEqual(0, count_excess_sensitive_fields([clean]))
