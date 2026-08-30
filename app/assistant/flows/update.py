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
from app.deploy.update import (
    UpdateCheckResult,
    check_for_updates,
    install_dependencies,
    pull_latest,
)
from app.deploy.update_state import update_store
from app.memory import repository
from app.runtime.activity import activity
from app.runtime.status_copy import (
    CANCELLED_UPDATE_DETAIL,
    CANCELLED_UPDATE_TITLE,
    NEEDS_CONFIRMATION_TITLE,
    PREPARING_CONFIRMATION_TITLE,
    PREPARING_UPDATE_DETAIL,
    UPDATE_UP_TO_DATE_MESSAGE,
    UPDATE_VOICE_PROMPT,
    UPDATING_DETAIL,
    UPDATING_TITLE,
    WAITING_UPDATE_CONFIRMATION_DETAIL,
    format_update_confirmation_prompt,
)
from app.system.reboot import schedule_service_restart

DEFAULT_UPDATE_CONVERSATION_ID = "default"


class UpdateInteractionHandler:
    """Handle mid-session software update confirmation flow."""

    def offer_update(
        self,
        *,
        result: UpdateCheckResult,
        conversation_id: str = DEFAULT_UPDATE_CONVERSATION_ID,
    ) -> None:
        if not result.behind or not result.remote_sha:
            return
        if pending_interactions.get(conversation_id) is not None:
            return

        prompt = format_update_confirmation_prompt(result.commits_behind)
        update_store.mark_prompt_offered(result.remote_sha)
        pending_interactions.set(
            conversation_id=conversation_id,
            kind="update_confirmation",
            payload={
                "commits_behind": result.commits_behind,
                "remote_sha": result.remote_sha,
                "branch": result.branch,
            },
        )
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=prompt,
        )
        activity.standby(
            title=NEEDS_CONFIRMATION_TITLE,
            detail=WAITING_UPDATE_CONFIRMATION_DETAIL,
            source="assistant.flows.update",
        )
        activity.announce_voice(UPDATE_VOICE_PROMPT)

    def start(
        self,
        *,
        conversation_id: str,
        message: str,
    ) -> ResponseSource:
        result = check_for_updates()
        update_store.record_check(result)
        if not result.behind:
            return answer_source(
                user_message=message,
                facts=UPDATE_UP_TO_DATE_MESSAGE,
                conversation_id=conversation_id,
            )

        if not update_store.should_prompt(result.remote_sha):
            return answer_source(
                user_message=message,
                facts=format_update_confirmation_prompt(result.commits_behind),
                conversation_id=conversation_id,
            )

        activity.working(
            title=PREPARING_CONFIRMATION_TITLE,
            detail=PREPARING_UPDATE_DETAIL,
            source="assistant.flows.update",
        )
        self.offer_update(result=result, conversation_id=conversation_id)
        return confirmation_source(
            user_message=message,
            facts=format_update_confirmation_prompt(result.commits_behind),
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
        if pending.kind != "update_confirmation":
            return None

        remote_sha = str(pending.payload.get("remote_sha", ""))

        if is_rejection_message(message):
            pending_interactions.clear(conversation_id)
            if remote_sha:
                update_store.dismiss(remote_sha)
            activity.standby(
                title=CANCELLED_UPDATE_TITLE,
                detail=CANCELLED_UPDATE_DETAIL,
                source="assistant.flows.update",
            )
            return answer_source(
                user_message=user_message,
                facts="Update dismissed.",
                conversation_id=conversation_id,
            )

        if not is_confirmation_message(message):
            return follow_up_source(
                user_message=user_message,
                facts="Reply yes to update and restart, or no to dismiss.",
                conversation_id=conversation_id,
            )

        pending_interactions.clear(conversation_id)
        activity.working(
            title=UPDATING_TITLE,
            detail=UPDATING_DETAIL,
            source="assistant.flows.update",
        )

        pull_result = pull_latest()
        if not pull_result.updated and pull_result.message != "Already up to date.":
            activity.standby(
                title=CANCELLED_UPDATE_TITLE,
                detail=CANCELLED_UPDATE_DETAIL,
                source="assistant.flows.update",
            )
            return answer_source(
                user_message=user_message,
                facts=f"I could not update: {pull_result.message}",
                conversation_id=conversation_id,
            )

        settings = get_settings()
        if settings.auto_update_install:
            install_dependencies()

        scheduled = schedule_service_restart()
        if not scheduled:
            activity.standby(
                title=CANCELLED_UPDATE_TITLE,
                detail=CANCELLED_UPDATE_DETAIL,
                source="assistant.flows.update",
            )
            return answer_source(
                user_message=user_message,
                facts=(
                    "The update was pulled, but service restart is disabled. "
                    "Set SERVICE_RESTART_ENABLED=true and restart manually."
                ),
                conversation_id=conversation_id,
            )

        return answer_source(
            user_message=user_message,
            facts="Updating now. I will restart shortly.",
            conversation_id=conversation_id,
            persist=False,
        )


update_interaction_handler = UpdateInteractionHandler()
