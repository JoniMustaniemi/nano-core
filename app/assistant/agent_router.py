from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.assistant.agent_rules import (
    is_health_check_request,
    is_note_add_request,
    is_note_list_request,
    is_note_lookup_request,
    is_pull_request_request,
    needs_wipe_confirmation,
    should_answer_without_tools,
)
from app.llm.protocol import LLMClient


@dataclass(frozen=True, slots=True)
class RouteDecision:
    mode: Literal["answer", "tool", "interaction", "planner"]
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    interaction: str | None = None


class AgentRouter:
    """
    Hybrid router that decides whether to answer, run a tool, start an interaction, or plan.
    """

    def decide(
        self,
        message: str,
        *,
        client: LLMClient,
        history: list[Any],
    ) -> RouteDecision:
        """
        Decide how to handle a new user message.

        Args:
            message: User message text.
            client: LLM client used for fallback routing.
            history: Conversation history records.

        Returns:
            Route decision for the orchestrator.
        """
        if needs_wipe_confirmation(message):
            return RouteDecision(mode="interaction", interaction="wipe")

        if is_note_add_request(message) or is_note_list_request(message) or is_note_lookup_request(
            message
        ):
            return RouteDecision(mode="interaction", interaction="note")

        if is_health_check_request(message):
            return RouteDecision(mode="tool", tool_name="check_health", tool_args={})

        if is_pull_request_request(message):
            return RouteDecision(mode="tool", tool_name="create_pull_request", tool_args={})

        if should_answer_without_tools(message):
            return RouteDecision(mode="answer")

        return RouteDecision(mode="planner")
