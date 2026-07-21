from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.assistant.agent_rules import (
    is_health_check_request,
    is_note_add_request,
    is_note_list_request,
    is_note_lookup_request,
    is_pull_request_request,
    is_timer_cancel_request,
    is_timer_start_request,
    is_timer_status_request,
    needs_timer_duration,
    needs_wipe_confirmation,
    should_answer_without_tools,
)
from app.assistant.pending import pending_interactions


@dataclass(frozen=True, slots=True)
class RouteDecision:
    mode: Literal["answer", "tool", "interaction", "planner", "pending"]
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    interaction: str | None = None


class AgentRouter:
    """
    Unified router for new user messages.

    Priority order:
    1. Timer status/cancel (clears pending timer follow-ups)
    2. Pending interaction resume
    3. Timer start/duration
    3. Wipe confirmation
    4. Note add/list/lookup
    5. Health check tool
    6. Pull request tool
    7. Direct answer without tools
    8. Planner fallback
    """

    def decide(
        self,
        message: str,
        *,
        conversation_id: str,
        history: list[Any],
    ) -> RouteDecision:
        """
        Decide how to handle a new user message.

        Args:
            message: User message text.
            conversation_id: Conversation identifier for pending-state lookup.
            history: Conversation history records.

        Returns:
            Route decision for the orchestrator.
        """
        _ = history
        if is_timer_status_request(message):
            pending_interactions.clear(conversation_id)
            return RouteDecision(mode="tool", tool_name="list_timers", tool_args={})

        if is_timer_cancel_request(message):
            pending_interactions.clear(conversation_id)
            return RouteDecision(mode="tool", tool_name="cancel_timers", tool_args={})

        if pending_interactions.get(conversation_id) is not None:
            return RouteDecision(mode="pending")

        if needs_timer_duration(message) or is_timer_start_request(message):
            return RouteDecision(mode="interaction", interaction="timer")

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
