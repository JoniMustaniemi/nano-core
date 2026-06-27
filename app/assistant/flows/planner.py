from __future__ import annotations

import json
from typing import Any

from app.assistant.agent_rules import parse_decision, tool_matches_request, tool_signature
from app.assistant.agent_types import ToolResult
from app.assistant.flows.chat import AgentChatFlow
from app.assistant.response_guard import enforce_user_facing_answer
from app.assistant.tool_runner import ToolRunner
from app.memory import repository
from app.runtime.activity import activity


class AgentPlanner:
    """
    Run the JSON tool-planning loop for non-deterministic agent requests.
    """

    def __init__(
        self,
        *,
        tool_runner: ToolRunner,
        chat_flow: AgentChatFlow,
    ) -> None:
        """
        Initialize the AgentPlanner instance.

        Args:
            tool_runner: Tool runner value.
            chat_flow: Chat fallback flow value.

        Returns:
            None.
        """
        self.tool_runner = tool_runner
        self.chat_flow = chat_flow

    def run(
        self,
        *,
        client: Any,
        conversation_id: str,
        message: str,
        history: list[Any],
        messages: list[dict[str, str]],
    ) -> str:
        """
        Run the planner until it returns a final answer or reaches a limit.

        Args:
            client: LLM client used to generate planner decisions.
            conversation_id: Conversation identifier used to scope history.
            message: User message or prompt text.
            history: Chat history records.
            messages: Planner messages.

        Returns:
            User-facing assistant answer.
        """
        activity.working(
            title="Nano is planning an action.",
            detail="Using the local model to decide whether to answer or run a tool.",
            source="assistant.flows.planner",
        )

        invalid_json_attempts = 0
        executed_tools: dict[str, ToolResult] = {}
        for _ in range(8):
            raw = client.complete(messages=messages)
            decision = parse_decision(raw)

            if decision["type"] == "final":
                return self._finish_response(
                    client=client,
                    user_message=message,
                    conversation_id=conversation_id,
                    content=decision["content"],
                )

            if decision["type"] != "tool_call":
                invalid_json_attempts += 1
                if invalid_json_attempts >= 2:
                    return self.chat_flow.fallback_to_chat(
                        client=client,
                        message=message,
                        conversation_id=conversation_id,
                        history=history,
                    )
                self._append_model_correction(
                    messages=messages,
                    raw=raw,
                    content="The previous response was not valid JSON. Return only a JSON object.",
                )
                continue

            tool_name = decision["tool"]
            args = decision["args"]
            if not tool_matches_request(message, tool_name):
                self._append_model_correction(
                    messages=messages,
                    raw=raw,
                    content=(
                        f"The tool call {tool_name} does not match the user's request. "
                        "Do not call a tool here. Return a final answer directly."
                    ),
                )
                continue

            signature = tool_signature(tool_name, args)
            existing_result = executed_tools.get(signature)
            if existing_result is not None:
                self._append_model_correction(
                    messages=messages,
                    raw=raw,
                    content=(
                        f"Tool {tool_name} was already called with the same arguments and "
                        f"returned:\n{existing_result.content}\n"
                        "Do not call the same tool again. Return a final answer now."
                    ),
                )
                continue

            activity.log(
                title=f"Nano called {tool_name}.",
                detail=json.dumps(args, ensure_ascii=False),
                source="assistant.flows.planner",
            )
            self.tool_runner.announce_call(tool_name)
            result = self.tool_runner.execute(tool_name, args)
            executed_tools[signature] = result
            self._append_model_result(messages=messages, raw=raw, result=result)

        fallback = "I tried to complete the task, but I hit the step limit."
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=fallback,
        )
        self.tool_runner.report_error(
            title="Nano could not finish the task.",
            detail=fallback,
            spoken_message="I could not finish the task.",
        )
        return fallback

    def _finish_response(
        self,
        *,
        client: Any,
        user_message: str,
        conversation_id: str,
        content: str,
    ) -> str:
        """
        Guard, persist, and return a final planner answer.

        Args:
            client: LLM client used to revise responses.
            user_message: User message or prompt text.
            conversation_id: Conversation identifier used to scope history.
            content: Draft final answer.

        Returns:
            User-facing assistant answer.
        """
        content = enforce_user_facing_answer(client, user_message, content)
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
        )
        activity.standby(
            title="Nano finished the task.",
            detail="The agent returned a final response.",
            source="assistant.flows.planner",
        )
        return content

    def _append_model_correction(
        self,
        *,
        messages: list[dict[str, str]],
        raw: str,
        content: str,
    ) -> None:
        """
        Add a system correction after an invalid or unsafe planner step.

        Args:
            messages: Planner messages to mutate.
            raw: Raw model response.
            content: Correction instruction.

        Returns:
            None.
        """
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "system", "content": content})

    def _append_model_result(
        self,
        *,
        messages: list[dict[str, str]],
        raw: str,
        result: ToolResult,
    ) -> None:
        """
        Add a tool result back into the planner conversation.

        Args:
            messages: Planner messages to mutate.
            raw: Raw tool-call response.
            result: Tool result value.

        Returns:
            None.
        """
        messages.append({"role": "assistant", "content": raw})
        messages.append(
            {
                "role": "system",
                "content": (
                    f"Tool {result.tool} returned:\n{result.content}\n"
                    "Use that result to continue or answer."
                ),
            }
        )
