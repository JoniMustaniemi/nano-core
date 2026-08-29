from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.assistant.pending import pending_interactions
from app.assistant.rules import (
    is_ambiguous_singular_stopwatch_stop,
    is_ambiguous_singular_timer_cancel,
    is_capability_question,
    is_clear_all_timers_request,
    is_health_check_request,
    is_identity_question,
    is_internal_note_list_request,
    is_pull_request_request,
    is_stopwatch_start_request,
    is_stopwatch_stop_request,
    is_system_analysis_request,
    is_timer_cancel_request,
    is_timer_start_request,
    is_timer_status_request,
    needs_reboot_confirmation,
    needs_service_restart_confirmation,
    needs_timer_duration,
    needs_wipe_confirmation,
    parse_stopwatch_rename_args,
    parse_stopwatch_stop_args,
    parse_timer_cancel_args,
    parse_timer_rename_args,
    should_answer_without_tools,
)
from app.memory import repository


@dataclass(frozen=True, slots=True)
class RouteDecision:
    mode: Literal[
        "answer",
        "capabilities",
        "direct",
        "identity",
        "tool",
        "interaction",
        "planner",
        "pending",
    ]

    tool_name: str | None = None

    tool_args: dict[str, Any] | None = None

    interaction: str | None = None

    direct_facts: str | None = None


class AgentRouter:
    """
    Unified router for new user messages.

    Priority order:
    1. Timer status (clears pending timer follow-ups)
    2. Clear all timers (clears pending timer follow-ups)
    3. Stopwatch stop (clears pending timer follow-ups)
    4. Timer cancel (clears pending timer follow-ups)
    4. Pending interaction resume
    5. Stopwatch start
    6. Timer start/duration
    7. Wipe confirmation
    8. Reboot confirmation
    9. Health check tool
    10. System analysis tool
    11. Pull request tool
    12. Internal note list tool
    13. Direct answer without tools
    14. Capabilities answer from tool catalog
    15. Identity answer with dynamic context
    16. Planner fallback
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

        if is_clear_all_timers_request(message):
            pending_interactions.clear(conversation_id)
            return RouteDecision(mode="tool", tool_name="clear_all_timers", tool_args={})

        stopwatch_rename_args = parse_stopwatch_rename_args(message)
        if stopwatch_rename_args is not None:
            pending_interactions.clear(conversation_id)
            return RouteDecision(
                mode="tool",
                tool_name="rename_stopwatch",
                tool_args=stopwatch_rename_args,
            )

        timer_rename_args = parse_timer_rename_args(message)
        if timer_rename_args is not None:
            pending_interactions.clear(conversation_id)
            return RouteDecision(
                mode="tool",
                tool_name="rename_timer",
                tool_args=timer_rename_args,
            )

        stopwatch_stop_args = parse_stopwatch_stop_args(message)
        if stopwatch_stop_args is not None:
            pending_interactions.clear(conversation_id)
            return RouteDecision(
                mode="tool",
                tool_name="stop_stopwatches",
                tool_args=stopwatch_stop_args,
            )

        if is_stopwatch_stop_request(message):
            pending_interactions.clear(conversation_id)
            if is_ambiguous_singular_stopwatch_stop(message):
                if len(repository.list_stopwatches()) > 1:
                    return RouteDecision(
                        mode="direct",
                        direct_facts=(
                            "Multiple stopwatches are running. Say stop stopwatch and the stopwatch id, "
                            "or stop stopwatches to clear all."
                        ),
                    )
            return RouteDecision(mode="tool", tool_name="stop_stopwatches", tool_args={})

        timer_cancel_args = parse_timer_cancel_args(message)
        if timer_cancel_args is not None:
            pending_interactions.clear(conversation_id)
            return RouteDecision(
                mode="tool",
                tool_name="cancel_timers",
                tool_args=timer_cancel_args,
            )

        if is_timer_cancel_request(message):
            pending_interactions.clear(conversation_id)
            if is_ambiguous_singular_timer_cancel(message):
                if len(repository.list_countdown_timers()) > 1:
                    return RouteDecision(
                        mode="direct",
                        direct_facts=(
                            "Multiple timers are running. Say cancel timer and the timer id, "
                            "or cancel timers to clear all."
                        ),
                    )
            return RouteDecision(mode="tool", tool_name="cancel_timers", tool_args={})

        if pending_interactions.get(conversation_id) is not None:
            return RouteDecision(mode="pending")

        if is_stopwatch_start_request(message):
            return RouteDecision(mode="tool", tool_name="start_stopwatch", tool_args={})

        if needs_timer_duration(message) or is_timer_start_request(message):
            return RouteDecision(mode="interaction", interaction="timer")

        if needs_wipe_confirmation(message):
            return RouteDecision(mode="interaction", interaction="wipe")

        if needs_service_restart_confirmation(message):
            return RouteDecision(mode="interaction", interaction="service_restart")

        if needs_reboot_confirmation(message):
            return RouteDecision(mode="interaction", interaction="reboot")

        if is_health_check_request(message):
            return RouteDecision(mode="tool", tool_name="check_health", tool_args={})

        if is_system_analysis_request(message):
            return RouteDecision(mode="tool", tool_name="analyze_system", tool_args={})

        if is_pull_request_request(message):
            return RouteDecision(mode="tool", tool_name="create_pull_request", tool_args={})

        if is_internal_note_list_request(message):
            return RouteDecision(mode="tool", tool_name="list_internal_notes", tool_args={})

        if is_capability_question(message):
            return RouteDecision(mode="capabilities")

        if is_identity_question(message):
            return RouteDecision(mode="identity")

        if should_answer_without_tools(message):
            return RouteDecision(mode="answer")

        return RouteDecision(mode="planner")
