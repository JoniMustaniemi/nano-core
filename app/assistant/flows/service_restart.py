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
    CANCELLED_SERVICE_RESTART_DETAIL,
    CANCELLED_SERVICE_RESTART_TITLE,
    NEEDS_CONFIRMATION_TITLE,
    PREPARING_CONFIRMATION_TITLE,
    PREPARING_SERVICE_RESTART_DETAIL,
    RESTARTING_SERVICE_DETAIL,
    RESTARTING_SERVICE_TITLE,
    SERVICE_RESTART_DISABLED_DETAIL,
    SERVICE_RESTART_DISABLED_TITLE,
    WAITING_SERVICE_RESTART_CONFIRMATION_DETAIL,
)
from app.system.reboot import schedule_service_restart


class ServiceRestartInteractionHandler:
    """Handle nano-core service restart confirmation flow."""

    def start(
        self,
        *,
        conversation_id: str,
        message: str,
    ) -> ResponseSource:
        settings = get_settings()
        if not settings.service_restart_enabled:
            activity.standby(
                title=SERVICE_RESTART_DISABLED_TITLE,
                detail=SERVICE_RESTART_DISABLED_DETAIL,
                source="assistant.flows.service_restart",
            )
            return answer_source(
                user_message=message,
                facts=(
                    "Service restart is disabled on this server. "
                    "Set SERVICE_RESTART_ENABLED=true to allow it."
                ),
                conversation_id=conversation_id,
            )

        activity.working(
            title=PREPARING_CONFIRMATION_TITLE,
            detail=PREPARING_SERVICE_RESTART_DETAIL,
            source="assistant.flows.service_restart",
        )
        pending_interactions.set(
            conversation_id=conversation_id,
            kind="service_restart_confirmation",
            payload={"request": message},
        )
        activity.standby(
            title=NEEDS_CONFIRMATION_TITLE,
            detail=WAITING_SERVICE_RESTART_CONFIRMATION_DETAIL,
            source="assistant.flows.service_restart",
        )
        return confirmation_source(
            user_message=message,
            facts=f'User requested: "{message.strip()}"',
            conversation_id=conversation_id,
            confirmation_action="service_restart",
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
        if pending.kind != "service_restart_confirmation":
            return None

        if is_rejection_message(message):
            pending_interactions.clear(conversation_id)
            activity.standby(
                title=CANCELLED_SERVICE_RESTART_TITLE,
                detail=CANCELLED_SERVICE_RESTART_DETAIL,
                source="assistant.flows.service_restart",
            )
            return answer_source(
                user_message=user_message,
                facts="Service restart cancelled.",
                conversation_id=conversation_id,
            )

        if not is_confirmation_message(message):
            return follow_up_source(
                user_message=user_message,
                facts="Reply yes to restart my service, or no to cancel.",
                conversation_id=conversation_id,
            )

        pending_interactions.clear(conversation_id)
        activity.working(
            title=RESTARTING_SERVICE_TITLE,
            detail=RESTARTING_SERVICE_DETAIL,
            source="assistant.flows.service_restart",
        )
        scheduled = schedule_service_restart()
        if not scheduled:
            activity.standby(
                title=SERVICE_RESTART_DISABLED_TITLE,
                detail=SERVICE_RESTART_DISABLED_DETAIL,
                source="assistant.flows.service_restart",
            )
            return answer_source(
                user_message=user_message,
                facts="Service restart is disabled on this server.",
                conversation_id=conversation_id,
            )

        return answer_source(
            user_message=user_message,
            facts="Restarting my service now.",
            conversation_id=conversation_id,
            persist=False,
        )
