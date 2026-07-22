"""Ollama chat adapter for the audited v3 runner."""


def _to_ollama_messages(messages: list[dict]) -> list[dict]:
    wire_messages = []
    for message in messages:
        wire = {key: value for key, value in message.items() if key != "tool_calls"}
        if message.get("tool_calls"):
            wire["tool_calls"] = [
                {"function": {"name": call["name"], "arguments": call.get("arguments", {})}}
                for call in message["tool_calls"]
            ]
        wire_messages.append(wire)
    return wire_messages


def _normalize_tool_calls(message: dict) -> list[dict]:
    calls = message.get("tool_calls", [])
    normalized = []
    for call in calls:
        function = call.get("function", call)
        if not isinstance(function, dict) or not function.get("name"):
            continue
        arguments = function.get("arguments", {})
        normalized.append({"name": function["name"], "arguments": arguments if isinstance(arguments, dict) else {}})
    return normalized


def make_ollama_model_step(
    *, request_post, model_name: str, tools: list[dict], url: str,
    seed: int, temperature: float, think: bool,
):
    """Create the normalized callback consumed by ``run_agent_turns``."""
    def model_step(messages: list[dict]) -> dict:
        response = request_post(
            url,
            json={
                "model": model_name,
                "messages": _to_ollama_messages(messages),
                "tools": tools,
                "stream": False,
                "think": think,
                "options": {"temperature": temperature, "seed": seed},
            },
            timeout=300,
        )
        response.raise_for_status()
        message = response.json().get("message", {})
        if not isinstance(message, dict):
            raise ValueError("Ollama response message must be an object")
        return {
            "content": message.get("content", "") or "",
            "tool_calls": _normalize_tool_calls(message),
        }
    return model_step
