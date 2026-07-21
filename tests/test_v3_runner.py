import json
import unittest

from v3_runner import run_agent_turns


class V3RunnerTests(unittest.TestCase):
    def test_runner_delivers_projected_tool_payload_and_emits_audit_event(self):
        responses = iter(
            [
                {"content": "", "tool_calls": [{"name": "get_contact", "arguments": {"id": "c1"}}]},
                {"content": "김민수와 일정을 조율하겠습니다.", "tool_calls": []},
            ]
        )
        received_messages = []

        def model_step(messages):
            received_messages.append(messages)
            return next(responses)

        def tool_executor(name, arguments):
            self.assertEqual(("get_contact", {"id": "c1"}), (name, arguments))
            return {"id": "c1", "name": "김민수", "phone": "010-1234-5678"}

        result = run_agent_turns(
            model_step=model_step,
            tool_executor=tool_executor,
            initial_messages=[{"role": "user", "content": "김민수 일정 확인"}],
            condition="C",
            projection_by_tool={"get_contact": ["id", "name"]},
            sensitive_fields_by_tool={"get_contact": {"phone"}},
            run_id="run-smoke",
            model="stub-model",
            scenario="v3_s1",
            seed=0,
            max_turns=3,
        )

        self.assertEqual("completed", result["status"])
        self.assertEqual("김민수와 일정을 조율하겠습니다.", result["final_output"])
        self.assertEqual(1, len(result["delivery_events"]))
        self.assertEqual(["phone"], result["delivery_events"][0]["removed_field_paths"])
        tool_message = received_messages[1][-1]
        self.assertEqual("tool", tool_message["role"])
        self.assertNotIn("010-1234-5678", tool_message["content"])
        self.assertEqual({"id": "c1", "name": "김민수"}, json.loads(tool_message["content"]))


if __name__ == "__main__":
    unittest.main()
