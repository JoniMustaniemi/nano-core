from __future__ import annotations

import json
from typing import Any

from app.assistant.agent_rules import (
    duration_args_from_message,
    needs_timer_duration,
    timer_confirmation,
)
from app.assistant.pending import PendingInteraction, pending_interactions
from app.assistant.response_source import (
    ResponseSource,
    confirmation_source,
    follow_up_source,
)
from app.assistant.tool_executor import ToolExecutor
from app.assistant.tool_runner import ToolRunner
from app.runtime.activity import activity


class TimerInteractionHandler:
    """
    Handle timer start requests and pending duration follow-ups.
    """

    def __init__(
        self,
        *,
        tool_runner: ToolRunner,
        tool_executor: ToolExecutor,
    ) -> None:
        """
        Initialize the TimerInteractionHandler instance.

        Args:
            tool_runner: Tool runner value.
            tool_executor: Tool executor value.
        """
        self.tool_runner = tool_runner
        self.tool_executor = tool_executor

    def handle_direct_request(
        self,
        *,
        message: str,
        conversation_id: str,
        user_message: str,
    ) -> ResponseSource | None:
        """
        Handle timer start requests routed by AgentRouter.

        Args:
            message: User message or prompt text.
            conversation_id: Conversation identifier used to scope history.
            user_message: Original user message.

        Returns:
            Timer response source when handled; otherwise None.
        """
        if needs_timer_duration(message):
            return self._request_timer_duration(
                conversation_id=conversation_id,
                user_message=user_message,
            )

        duration_args = duration_args_from_message(message)
        if duration_args is not None:
            return self._run_timer_request(
                conversation_id=conversation_id,
                user_message=user_message,
                args=duration_args,
            )

        return self._request_timer_duration(
            conversation_id=conversation_id,
            user_message=user_message,
        )

    def handle_pending(
        self,
        *,
        pending: PendingInteraction,
        message: str,
        conversation_id: str,
        user_message: str,
    ) -> ResponseSource | None:
        """
        Continue a pending timer duration request.

        Args:
            pending: Pending interaction.
            message: User message or prompt text.
            conversation_id: Conversation identifier used to scope history.
            user_message: Original user message.

        Returns:
            Timer response source when handled; otherwise None.
        """
        if pending.kind != "timer_duration":
            return None

        duration_args = duration_args_from_message(message)
        if duration_args is None:
            return follow_up_source(
                user_message=user_message,
                facts="Specify the timer duration in seconds or minutes.",
                conversation_id=conversation_id,
            )

        pending_interactions.clear(conversation_id)
        return self._run_timer_request(
            conversation_id=conversation_id,
            user_message=user_message,
            args=duration_args,
        )

    def _request_timer_duration(
        self,
        *,
        conversation_id: str,
        user_message: str,
    ) -> ResponseSource:
        """
        Ask the user for a missing timer duration.

        Args:
            conversation_id: Conversation identifier used to scope history.
            user_message: Original user message.

        Returns:
            Follow-up response source.
        """
        pending_interactions.set(
            conversation_id=conversation_id,
            kind="timer_duration",
            payload={"request": user_message},
        )
        activity.standby(
            title="Nano needs one detail.",
            detail="Waiting for the timer duration.",
            source="assistant.flows.timer",
        )
        return follow_up_source(
            user_message=user_message,
            facts="How long should the timer run?",
            conversation_id=conversation_id,
        )

    def _run_timer_request(
        self,
        *,
        conversation_id: str,
        user_message: str,
        args: dict[str, Any],
    ) -> ResponseSource:
        """
        Start a timer and return a confirmation response source.

        Args:
            conversation_id: Conversation identifier used to scope history.
            user_message: Original user message.
            args: Timer tool arguments.

        Returns:
            Timer confirmation response source.
        """
        activity.working(
            title="Nano is setting a timer.",
            detail="Scheduling the requested timer.",
            source="assistant.flows.timer",
        )
        activity.log(
            title="Nano called start_timer.",
            detail=json.dumps(args, ensure_ascii=False),
            source="assistant.flows.timer",
        )
        self.tool_runner.announce_call("start_timer")
        self.tool_runner.execute("start_timer", args)
        return confirmation_source(
            user_message=user_message,
            facts=timer_confirmation(args),
            conversation_id=conversation_id,
        )
