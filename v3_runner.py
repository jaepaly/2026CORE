"""Dependency-injected v3 agent loop for audited tool delivery."""

import json

from agent_v3 import apply_policy_to_tool_result


def run_agent_turns(
    *,
    model_step,
    tool_executor,
    initial_messages: list[dict],
    condition: str,
    projection_by_tool: dict[str, list[str]],
    sensitive_fields_by_tool: dict[str, set[str]],
    run_id: str,
    model: str,
    scenario: str,
    seed: int,
    max_turns: int,
) -> dict:
    messages = list(initial_messages)
    delivery_events = []
    for turn in range(1, max_turns + 1):
        response = model_step(list(messages))
        tool_calls = response.get("tool_calls", [])
        content = response.get("content", "")
        messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
        if not tool_calls:
            return {
                "status": "completed",
                "final_output": content,
                "messages": messages,
                "delivery_events": delivery_events,
            }
        for call in tool_calls:
            name = call["name"]
            arguments = call.get("arguments", {})
            raw_result = tool_executor(name, arguments)
            delivered, event = apply_policy_to_tool_result(
                condition=condition,
                projection_by_tool=projection_by_tool,
                sensitive_field_paths=sensitive_fields_by_tool.get(name, set()),
                raw_result=raw_result,
                run_id=run_id,
                model=model,
                scenario=scenario,
                seed=seed,
                turn=turn,
                tool_name=name,
                requested_args=arguments,
            )
            delivery_events.append(event)
            messages.append({"role": "tool", "content": json.dumps(delivered, ensure_ascii=False)})
    return {
        "status": "max_turns_reached",
        "final_output": "",
        "messages": messages,
        "delivery_events": delivery_events,
    }
