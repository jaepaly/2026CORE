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


def _run(model_step, tool_executor, *, max_turns=3, system_prompt=None):
    return run_agent_turns(
        model_step=model_step, tool_executor=tool_executor,
        initial_messages=[{"role": "user", "content": "과제"}], condition="A",
        projection_by_tool={}, sensitive_fields_by_tool={}, run_id="r",
        model="stub", scenario="v3_s1", seed=0, max_turns=max_turns,
        system_prompt=system_prompt,
    )


class RunStatusTests(unittest.TestCase):
    def test_exhausting_the_turn_budget_reports_max_turns_reached(self):
        call = {"name": "get_contact", "arguments": {"id": "c1"}}

        result = _run(lambda messages: {"content": "", "tool_calls": [call]},
                      lambda name, args: {"id": "c1"}, max_turns=2)

        self.assertEqual("max_turns_reached", result["status"])
        self.assertEqual(2, len(result["delivery_events"]))
        self.assertEqual(["get_contact", "get_contact"], result["executed_tools"])


class TechnicalFailureTests(unittest.TestCase):
    """A fault is captured per run, never raised past the caller."""

    def test_model_transport_fault_becomes_a_recorded_technical_failure(self):
        def model_step(messages):
            raise ConnectionError("connection refused to 10.0.0.5")

        result = _run(model_step, lambda name, args: {})

        self.assertEqual("technical_failure", result["status"])
        self.assertEqual("model_step", result["failure_stage"])
        self.assertEqual("ConnectionError", result["failure_type"])
        self.assertEqual(1, result["failure_turn"])

    def test_tool_fault_becomes_a_recorded_technical_failure(self):
        def tool_executor(name, arguments):
            raise RuntimeError("boom")

        result = _run(
            lambda messages: {"content": "", "tool_calls": [{"name": "get_contact", "arguments": {}}]},
            tool_executor,
        )

        self.assertEqual("technical_failure", result["status"])
        self.assertEqual("tool_call", result["failure_stage"])
        self.assertEqual("RuntimeError", result["failure_type"])

    def test_malformed_tool_call_object_does_not_escape_as_an_exception(self):
        result = _run(
            lambda messages: {"content": "", "tool_calls": [None]},
            lambda name, args: {},
        )

        self.assertEqual("technical_failure", result["status"])
        self.assertEqual("tool_call", result["failure_stage"])

    def test_fault_metadata_does_not_leak_the_exception_message(self):
        secret = "010-1234-5678"

        def model_step(messages):
            raise ValueError(f"payload was {secret}")

        result = _run(model_step, lambda name, args: {})

        self.assertNotIn(secret, str(result))
        self.assertNotIn("payload was", str(result))


class SystemPromptTests(unittest.TestCase):
    def test_system_prompt_is_prepended_once_ahead_of_the_task(self):
        seen = []

        def model_step(messages):
            seen.append(list(messages))
            return {"content": "끝", "tool_calls": []}

        _run(model_step, lambda name, args: {}, system_prompt="중립 지시")

        self.assertEqual("system", seen[0][0]["role"])
        self.assertEqual("중립 지시", seen[0][0]["content"])
        self.assertEqual("user", seen[0][1]["role"])


if __name__ == "__main__":
    unittest.main()
