from __future__ import annotations

from typing import Any

from app.assistant.agent_rules import parse_decision, tool_matches_request, tool_signature
from app.assistant.agent_types import AnswerIntentDecision, FinalDecision, ToolResult
from app.assistant.answer_executor import AnswerExecutor
from app.assistant.flows.chat import AgentChatFlow
from app.assistant.response_source import ResponseSource, answer_source, tool_result_source
from app.assistant.tool_runner import ToolRunner
from app.llm.protocol import LLMClient
from app.runtime.activity import activity
from app.runtime.status_copy import (
    COULD_NOT_FINISH_TITLE,
    PLANNING_ACTION_DETAIL,
    PLANNING_ACTION_TITLE,
    failed_tool_title,
    ran_tool_title,
)


class AgentPlanner:
    """
    Run the JSON tool-planning loop for non-deterministic agent requests.
    """

    def __init__(
        self,
        *,
        tool_runner: ToolRunner,
        chat_flow: AgentChatFlow,
        answer_executor: AnswerExecutor | None = None,
    ) -> None:
        """
        Initialize the AgentPlanner instance.

        Args:
            tool_runner: Tool runner value.
            chat_flow: Chat fallback flow value.
            answer_executor: Answer executor used for planner fallbacks.

        Returns:
            None.
        """
        self.tool_runner = tool_runner
        self.chat_flow = chat_flow
        self.answer_executor = answer_executor or AnswerExecutor()

    def run(
        self,
        *,
        client: LLMClient,
        conversation_id: str,
        message: str,
        history: list[Any],
        messages: list[dict[str, str]],
    ) -> ResponseSource:
        """
        Run the planner until it can build a response source or reaches a limit.

        Args:
            client: LLM client used to generate planner decisions.
            conversation_id: Conversation identifier used to scope history.
            message: User message or prompt text.
            history: Chat history records.
            messages: Planner messages.

        Returns:
            Structured response source for composition.
        """
        activity.working(
            title=PLANNING_ACTION_TITLE,
            detail=PLANNING_ACTION_DETAIL,
            source="assistant.flows.planner",
        )

        invalid_json_attempts = 0
        executed_tools: dict[str, ToolResult] = {}
        for _ in range(8):
            activity.working(
                title=PLANNING_ACTION_TITLE,
                detail=PLANNING_ACTION_DETAIL,
                source="assistant.flows.planner",
            )
            raw = client.complete(messages=messages)
            decision = parse_decision(raw)

            if decision["type"] in {"final", "answer_intent"}:
                return self._build_answer_source(
                    client=client,
                    message=message,
                    conversation_id=conversation_id,
                    history=history,
                    decision=decision,
                    executed_tools=executed_tools,
                )

            if decision["type"] != "tool_call":
                invalid_json_attempts += 1
                if invalid_json_attempts >= 2:
                    return self.answer_executor.draft(
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
                        "Do not call a tool here. Return answer_intent when ready."
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
                        "Do not call the same tool again. Return answer_intent when ready."
                    ),
                )
                continue

            result = self.tool_runner.execute(tool_name, args)
            executed_tools[signature] = result
            if result.ok:
                activity.log(
                    title=ran_tool_title(tool_name),
                    detail="Done.",
                    source="assistant.flows.planner",
                )
            else:
                activity.log(
                    title=failed_tool_title(tool_name),
                    detail="The tool reported a failure.",
                    source="assistant.flows.planner",
                )
            self._append_model_result(messages=messages, raw=raw, result=result)

        fallback = "I tried to complete the task, but I hit the step limit."
        self.tool_runner.report_error(
            title=COULD_NOT_FINISH_TITLE,
            detail=fallback,
            spoken_message="I could not finish the task.",
        )
        return answer_source(
            user_message=message,
            facts=fallback,
            conversation_id=conversation_id,
        )

    def _build_answer_source(
        self,
        *,
        client: LLMClient,
        message: str,
        conversation_id: str,
        history: list[Any],
        decision: AnswerIntentDecision | FinalDecision,
        executed_tools: dict[str, ToolResult],
    ) -> ResponseSource:
        """
        Build a response source from a planner answer intent.

        Args:
            client: LLM client used for answer fallbacks.
            message: User message text.
            conversation_id: Conversation identifier.
            history: Conversation history records.
            decision: Parsed planner decision.
            executed_tools: Executed tool results keyed by signature.

        Returns:
            Structured response source.
        """
        _ = client
        _ = history
        if executed_tools:
            latest = next(reversed(executed_tools.values()))
            if latest.tool == "draft_improvement_plan":
                return tool_result_source(
                    user_message=message,
                    facts=latest.content,
                    tool_name=latest.tool,
                    conversation_id=conversation_id,
                )

        content = decision.get("content")
        if isinstance(content, str) and content.strip():
            return answer_source(
                user_message=message,
                facts=content,
                conversation_id=conversation_id,
            )

        if executed_tools:
            latest = next(reversed(executed_tools.values()))
            return tool_result_source(
                user_message=message,
                facts=latest.content,
                tool_name=latest.tool,
                conversation_id=conversation_id,
            )

        return self.answer_executor.draft(
            client=client,
            message=message,
            conversation_id=conversation_id,
            history=history,
        )

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
                    "Use that result to continue or return answer_intent when ready."
                ),
            }
        )
