from __future__ import annotations

from typing import Any

from app.assistant.agent_rules import (
    is_confirmation_message,
    is_rejection_message,
    normalize_wipe_request,
)
from app.assistant.pending import PendingInteraction, pending_interactions
from app.assistant.response_source import (
    ResponseSource,
    answer_source,
    confirmation_source,
    follow_up_source,
)
from app.memory import repository
from app.proactive.store import proactive_store
from app.runtime.activity import activity
from app.runtime.status_copy import (
    CANCELLED_WIPE_TITLE,
    NEEDS_CONFIRMATION_TITLE,
    PREPARING_CONFIRMATION_TITLE,
    PREPARING_WIPE_DETAIL,
    WAITING_WIPE_CONFIRMATION_DETAIL,
    WIPE_CANCELLED_DETAIL,
    WIPED_MEMORY_DETAIL,
    WIPED_MEMORY_TITLE,
    WIPING_MEMORY_DETAIL,
    WIPING_MEMORY_TITLE,
)


class WipeInteractionHandler:
    """
    Handle destructive database wipe confirmation flow.
    """

    def start(
        self,
        *,
        conversation_id: str,
        message: str,
    ) -> ResponseSource:
        """
        Start a wipe confirmation interaction.

        Args:
            conversation_id: Conversation identifier used to scope history.
            message: User message or prompt text.

        Returns:
            Confirmation response source.
        """
        activity.working(
            title=PREPARING_CONFIRMATION_TITLE,
            detail=PREPARING_WIPE_DETAIL,
            source="assistant.flows.wipe",
        )
        pending_interactions.set(
            conversation_id=conversation_id,
            kind="wipe_confirmation",
            payload={"request": message},
        )
        activity.standby(
            title=NEEDS_CONFIRMATION_TITLE,
            detail=WAITING_WIPE_CONFIRMATION_DETAIL,
            source="assistant.flows.wipe",
        )
        return confirmation_source(
            user_message=message,
            facts=f'User requested: "{normalize_wipe_request(message)}"',
            conversation_id=conversation_id,
        )

    def handle_direct_request(self, **kwargs: Any) -> ResponseSource | None:
        """Wipe requests are started via `start()` from the orchestrator."""
        return None

    def handle_pending(
        self,
        *,
        pending: PendingInteraction,
        message: str,
        conversation_id: str,
        user_message: str,
    ) -> ResponseSource | None:
        """
        Continue a pending wipe confirmation interaction.

        Args:
            pending: Pending interaction.
            message: User message or prompt text.
            conversation_id: Conversation identifier used to scope history.
            user_message: Original user message.

        Returns:
            Wipe response source when handled; otherwise None.
        """
        if pending.kind != "wipe_confirmation":
            return None

        if is_rejection_message(message):
            pending_interactions.clear(conversation_id)
            activity.standby(
                title=CANCELLED_WIPE_TITLE,
                detail=WIPE_CANCELLED_DETAIL,
                source="assistant.flows.wipe",
            )
            return answer_source(
                user_message=user_message,
                facts="Database wipe cancelled.",
                conversation_id=conversation_id,
            )

        if not is_confirmation_message(message):
            return follow_up_source(
                user_message=user_message,
                facts="Reply yes to confirm the database wipe, or no to cancel.",
                conversation_id=conversation_id,
            )

        activity.working(
            title=WIPING_MEMORY_TITLE,
            detail=WIPING_MEMORY_DETAIL,
            source="assistant.flows.wipe",
        )
        repository.wipe_database()
        proactive_store.reset()
        pending_interactions.reset()
        activity.standby(
            title=WIPED_MEMORY_TITLE,
            detail=WIPED_MEMORY_DETAIL,
            source="assistant.flows.wipe",
        )
        return answer_source(
            user_message=user_message,
            facts="Database wiped.",
            conversation_id=conversation_id,
            persist=False,
        )
