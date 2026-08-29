from __future__ import annotations

from typing import Any

from app.assistant.pending import PendingInteraction, pending_interactions
from app.assistant.response_source import (
    ResponseSource,
    answer_source,
    confirmation_source,
    follow_up_source,
)
from app.assistant.rules import is_confirmation_message, is_rejection_message
from app.config import get_settings
from app.runtime.activity import activity
from app.runtime.status_copy import (
    CANCELLED_REBOOT_DETAIL,
    CANCELLED_REBOOT_TITLE,
    NEEDS_CONFIRMATION_TITLE,
    PREPARING_CONFIRMATION_TITLE,
    PREPARING_REBOOT_DETAIL,
    REBOOTING_DETAIL,
    REBOOTING_TITLE,
    REBOOT_DISABLED_DETAIL,
    REBOOT_DISABLED_TITLE,
    WAITING_REBOOT_CONFIRMATION_DETAIL,
)
from app.system.reboot import schedule_reboot


class RebootInteractionHandler:
    """Handle Raspberry Pi reboot confirmation flow."""

    def start(
        self,
        *,
        conversation_id: str,
        message: str,
    ) -> ResponseSource:
        settings = get_settings()
        if not settings.reboot_enabled:
            activity.standby(
                title=REBOOT_DISABLED_TITLE,
                detail=REBOOT_DISABLED_DETAIL,
                source="assistant.flows.reboot",
            )
            return answer_source(
                user_message=message,
                facts="Reboot is disabled on this server. Set REBOOT_ENABLED=true to allow it.",
                conversation_id=conversation_id,
            )

        activity.working(
            title=PREPARING_CONFIRMATION_TITLE,
            detail=PREPARING_REBOOT_DETAIL,
            source="assistant.flows.reboot",
        )
        pending_interactions.set(
            conversation_id=conversation_id,
            kind="reboot_confirmation",
            payload={"request": message},
        )
        activity.standby(
            title=NEEDS_CONFIRMATION_TITLE,
            detail=WAITING_REBOOT_CONFIRMATION_DETAIL,
            source="assistant.flows.reboot",
        )
        return confirmation_source(
            user_message=message,
            facts=f'User requested: "{message.strip()}"',
            conversation_id=conversation_id,
        )

    def handle_direct_request(self, **kwargs: Any) -> ResponseSource | None:
        return None

    def handle_pending(
        self,
        *,
        pending: PendingInteraction,
        message: str,
        conversation_id: str,
        user_message: str,
    ) -> ResponseSource | None:
        if pending.kind != "reboot_confirmation":
            return None

        if is_rejection_message(message):
            pending_interactions.clear(conversation_id)
            activity.standby(
                title=CANCELLED_REBOOT_TITLE,
                detail=CANCELLED_REBOOT_DETAIL,
                source="assistant.flows.reboot",
            )
            return answer_source(
                user_message=user_message,
                facts="Reboot cancelled.",
                conversation_id=conversation_id,
            )

        if not is_confirmation_message(message):
            return follow_up_source(
                user_message=user_message,
                facts="Reply yes to reboot the Raspberry Pi, or no to cancel.",
                conversation_id=conversation_id,
            )

        pending_interactions.clear(conversation_id)
        activity.working(
            title=REBOOTING_TITLE,
            detail=REBOOTING_DETAIL,
            source="assistant.flows.reboot",
        )
        scheduled = schedule_reboot()
        if not scheduled:
            activity.standby(
                title=REBOOT_DISABLED_TITLE,
                detail=REBOOT_DISABLED_DETAIL,
                source="assistant.flows.reboot",
            )
            return answer_source(
                user_message=user_message,
                facts="Reboot is disabled on this server.",
                conversation_id=conversation_id,
            )

        return answer_source(
            user_message=user_message,
            facts="Rebooting the Raspberry Pi now.",
            conversation_id=conversation_id,
            persist=False,
        )
