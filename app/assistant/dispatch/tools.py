from __future__ import annotations

from typing import Any

from app.assistant.agent_router import RouteDecision
from app.assistant.answer_executor import AnswerExecutor
from app.assistant.flows.planner import AgentPlanner
from app.assistant.response_source import ResponseSource, answer_source
from app.assistant.tool_executor import ToolExecutor
from app.llm.protocol import LLMClient


class RouteDispatcher:
    def __init__(
        self,
        *,
        tool_executor: ToolExecutor,
        answer_executor: AnswerExecutor,
        planner: AgentPlanner,
    ) -> None:
        self.tool_executor = tool_executor
        self.answer_executor = answer_executor
        self.planner = planner

    def dispatch(
        self,
        *,
        decision: RouteDecision,
        client: LLMClient,
        message: str,
        conversation_id: str,
        history: list[Any],
        messages: list[dict[str, str]] | None = None,
    ) -> ResponseSource:
        if decision.mode == "tool":
            return self.tool_executor.run(
                user_message=message,
                conversation_id=conversation_id,
                tool_name=decision.tool_name or "",
                args=decision.tool_args or {},
            )

        if decision.mode == "direct":
            return answer_source(
                user_message=message,
                facts=decision.direct_facts or "",
                conversation_id=conversation_id,
            )

        if decision.mode == "capabilities":
            return self.answer_executor.draft_capabilities(
                client=client,
                message=message,
                conversation_id=conversation_id,
            )

        if decision.mode == "identity":
            return self.answer_executor.draft_identity(
                client=client,
                message=message,
                conversation_id=conversation_id,
                history=history,
            )

        if decision.mode == "answer":
            return self.answer_executor.draft(
                client=client,
                message=message,
                conversation_id=conversation_id,
                history=history,
            )

        return self.planner.run(
            client=client,
            conversation_id=conversation_id,
            message=message,
            history=history,
            messages=messages or [],
        )
