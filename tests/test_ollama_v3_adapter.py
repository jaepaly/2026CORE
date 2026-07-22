import unittest

from ollama_v3_adapter import make_ollama_model_step


class OllamaV3AdapterTests(unittest.TestCase):
    def test_adapter_normalizes_ollama_tool_calls_and_serializes_prior_calls(self):
        captured = {}

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "message": {
                        "content": "",
                        "tool_calls": [{"function": {"name": "get_contact", "arguments": {"id": "c1"}}}],
                    }
                }

        def post(url, json, timeout):
            captured.update({"url": url, "payload": json, "timeout": timeout})
            return Response()

        step = make_ollama_model_step(
            request_post=post, model_name="stub-model", tools=[{"type": "function"}],
            url="http://ollama.test/api/chat", seed=7, temperature=0.2, think=False,
        )
        result = step([{
            "role": "assistant", "content": "", "tool_calls": [
                {"name": "search_contacts", "arguments": {"query": "김민수"}}
            ],
        }])

        self.assertEqual("http://ollama.test/api/chat", captured["url"])
        self.assertEqual("stub-model", captured["payload"]["model"])
        self.assertEqual({"temperature": 0.2, "seed": 7}, captured["payload"]["options"])
        wire_call = captured["payload"]["messages"][0]["tool_calls"][0]
        self.assertEqual("search_contacts", wire_call["function"]["name"])
        self.assertEqual({"query": "김민수"}, wire_call["function"]["arguments"])
        self.assertEqual([{"name": "get_contact", "arguments": {"id": "c1"}}], result["tool_calls"])


if __name__ == "__main__":
    unittest.main()
