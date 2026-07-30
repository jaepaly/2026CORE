"""Dependency-injected v3 agent loop for audited tool delivery.

Run outcomes are split into three statuses because the protocol treats them
differently (`docs/experiment_design_v3.md`):

``completed``
    The model stopped calling tools and produced a final answer.

``max_turns_reached``
    The model kept calling tools until the turn budget ran out.  This is an
    *agent* outcome, not a measurement fault, so it stays in the endpoint
    denominator as a failed run.  Excluding it would drop runs at a
    condition-dependent rate -- a projected condition can plausibly loop more --
    and bias the primary A-vs-C comparison through differential dropout.

``technical_failure``
    Transport, response-shape, or tool-execution fault.  Excluded from endpoint
    denominators and retried under a new ``retry_index``.  Faults are captured
    per run rather than raised so one malformed response cannot abort an
    experiment and discard every summary collected so far.  Only the exception
    type and turn are recorded: an exception message can quote tool payloads.
"""

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
    system_prompt: str | None = None,
    denied_tools: "frozenset[str] | set[str] | None" = None,
) -> dict:
    messages = list(initial_messages)
    if system_prompt is not None:
        messages.insert(0, {"role": "system", "content": system_prompt})
    delivery_events = []
    executed_tools: list[str] = []

    def technical_failure(stage: str, turn: int, error: Exception) -> dict:
        return {
            "status": "technical_failure",
            "final_output": "",
            "messages": messages,
            "delivery_events": delivery_events,
            "executed_tools": executed_tools,
            "failure_stage": stage,
            "failure_type": type(error).__name__,
            "failure_turn": turn,
        }

    for turn in range(1, max_turns + 1):
        try:
            response = model_step(list(messages))
            tool_calls = response.get("tool_calls", [])
            content = response.get("content", "")
        except Exception as error:  # noqa: BLE001 - recorded, not swallowed
            return technical_failure("model_step", turn, error)

        messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
        if not tool_calls:
            return {
                "status": "completed",
                "final_output": content,
                "messages": messages,
                "delivery_events": delivery_events,
                "executed_tools": executed_tools,
            }

        for call in tool_calls:
            try:
                name = call["name"]
                arguments = call.get("arguments", {})
                executed_tools.append(name)
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
                    denied_tools=denied_tools,
                )
            except Exception as error:  # noqa: BLE001 - recorded, not swallowed
                return technical_failure("tool_call", turn, error)

            delivery_events.append(event)
            messages.append({
                "role": "tool",
                "content": json.dumps(delivered, ensure_ascii=False),
            })

    return {
        "status": "max_turns_reached",
        "final_output": "",
        "messages": messages,
        "delivery_events": delivery_events,
        "executed_tools": executed_tools,
    }
