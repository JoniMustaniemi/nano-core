from __future__ import annotations

import json
from typing import Any

from app.assistant.agent_rules import (
    duration_args_from_message,
    is_timer_cancel_request,
    is_timer_start_request,
    is_timer_status_request,
    needs_timer_duration,
    timer_confirmation,
)
from app.assistant.flows.direct_tool import DirectToolHandler
from app.assistant.pending import PendingInteraction, pending_interactions
from app.assistant.tool_runner import ToolRunner
from app.memory import repository
from app.runtime.activity import activity


class TimerInteractionHandler:
    """
    Handle timer-specific direct requests and pending duration follow-ups.
    """

    def __init__(
        self,
        *,
        tool_runner: ToolRunner,
        direct_tool_handler: DirectToolHandler,
    ) -> None:
        """
        Initialize the TimerInteractionHandler instance.

        Args:
            tool_runner: Tool runner value.
            direct_tool_handler: Direct tool handler value.

        Returns:
            None.
        """
        self.tool_runner = tool_runner
        self.direct_tool_handler = direct_tool_handler

    def handle_direct_request(
        self,
        *,
        client: Any,
        message: str,
        conversation_id: str,
    ) -> str | None:
        """
        Handle timer requests that should bypass the planner.

        Args:
            client: LLM client used for direct tool handling.
            message: User message or prompt text.
            conversation_id: Conversation identifier used to scope history.

        Returns:
            Timer response when handled; otherwise None.
        """
        if is_timer_status_request(message):
            pending_interactions.clear(conversation_id)
            return self.direct_tool_handler.run(
                client=client,
                conversation_id=conversation_id,
                user_message=message,
                tool_name="list_timers",
                args={},
            )

        if is_timer_cancel_request(message):
            pending_interactions.clear(conversation_id)
            return self.direct_tool_handler.run(
                client=client,
                conversation_id=conversation_id,
                user_message=message,
                tool_name="cancel_timers",
                args={},
            )

        if needs_timer_duration(message):
            return self._request_timer_duration(
                conversation_id=conversation_id,
                message=message,
            )

        if is_timer_start_request(message):
            duration_args = duration_args_from_message(message)
            if duration_args is not None:
                return self._run_timer_request(
                    conversation_id=conversation_id,
                    args=duration_args,
                )

        return None

    def handle_pending(
        self,
        *,
        pending: PendingInteraction,
        message: str,
        conversation_id: str,
    ) -> str | None:
        """
        Continue a pending timer duration request.

        Args:
            pending: Pending interaction.
            message: User message or prompt text.
            conversation_id: Conversation identifier used to scope history.

        Returns:
            Timer response when handled; otherwise None.
        """
        if pending.kind != "timer_duration":
            return None

        duration_args = duration_args_from_message(message)
        if duration_args is None:
            follow_up = "Specify the timer duration in seconds or minutes."
            repository.add_chat_message(
                conversation_id=conversation_id,
                role="assistant",
                content=follow_up,
            )
            activity.standby(
                title="Nano needs one detail.",
                detail="Waiting for a valid timer duration.",
                source="assistant.flows.timer",
            )
            return follow_up

        pending_interactions.clear(conversation_id)
        return self._run_timer_request(
            conversation_id=conversation_id,
            args=duration_args,
        )

    def _request_timer_duration(self, *, conversation_id: str, message: str) -> str:
        """
        Ask the user for a missing timer duration.

        Args:
            conversation_id: Conversation identifier used to scope history.
            message: User message or prompt text.

        Returns:
            Follow-up question.
        """
        follow_up = "How long should the timer run?"
        pending_interactions.set(
            conversation_id=conversation_id,
            kind="timer_duration",
            payload={"request": message},
        )
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=follow_up,
        )
        activity.standby(
            title="Nano needs one detail.",
            detail="Waiting for the timer duration.",
            source="assistant.flows.timer",
        )
        return follow_up

    def _run_timer_request(
        self,
        *,
        conversation_id: str,
        args: dict[str, Any],
    ) -> str:
        """
        Start a timer and return a friendly confirmation.

        Args:
            conversation_id: Conversation identifier used to scope history.
            args: Timer tool arguments.

        Returns:
            Timer confirmation text.
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
        result = self.tool_runner.execute("start_timer", args)
        confirmation = timer_confirmation(args)
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=confirmation,
        )
        activity.standby(
            title="Nano finished the task.",
            detail=result.content,
            source="assistant.flows.timer",
        )
        return confirmation
