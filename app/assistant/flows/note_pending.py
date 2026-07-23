from __future__ import annotations

from app.assistant.agent_rules import (
    is_note_add_request,
    is_rejection_message,
    note_content_from_message,
)
from app.assistant.pending import PendingInteraction, pending_interactions
from app.assistant.response_source import (
    ResponseSource,
    confirmation_source,
    follow_up_source,
    tool_result_source,
)
from app.runtime.activity import activity
from app.runtime.status_copy import CANCELLED_NOTE_TITLE, NO_NOTE_SAVED_DETAIL


class NotePendingMixin:
    """Pending multi-turn note interactions."""

    def handle_pending(
        self,
        *,
        pending: PendingInteraction,
        message: str,
        conversation_id: str,
        user_message: str,
    ) -> ResponseSource | None:
        if pending.kind == "note_content":
            return self._complete_pending_note_request(
                message=message,
                conversation_id=conversation_id,
                user_message=user_message,
            )

        if pending.kind == "note_name":
            return self._complete_pending_note_name(
                pending=pending,
                message=message,
                conversation_id=conversation_id,
                user_message=user_message,
            )

        if pending.kind == "note_selection":
            return self._complete_pending_note_selection(
                pending=pending,
                message=message,
                conversation_id=conversation_id,
                user_message=user_message,
            )

        return None

    def _complete_pending_note_request(
        self,
        *,
        message: str,
        conversation_id: str,
        user_message: str,
    ) -> ResponseSource | None:
        if is_rejection_message(message):
            return self._cancel_pending_note(
                conversation_id=conversation_id,
                user_message=user_message,
            )

        content = note_content_from_message(message) if is_note_add_request(message) else message
        resolved_content = content or ""
        pending = pending_interactions.get(conversation_id)
        name = str((pending.payload if pending else {}).get("name", "")).strip()
        return self._save_note(
            conversation_id=conversation_id,
            name=name,
            content=resolved_content,
            user_message=user_message,
        )

    def _complete_pending_note_name(
        self,
        *,
        pending: PendingInteraction,
        message: str,
        conversation_id: str,
        user_message: str,
    ) -> ResponseSource | None:
        if is_rejection_message(message):
            return self._cancel_pending_note(
                conversation_id=conversation_id,
                user_message=user_message,
            )

        name = message.strip()
        content = str(pending.payload.get("content", "")).strip()
        if content:
            return self._save_note(
                conversation_id=conversation_id,
                name=name,
                content=content,
                user_message=user_message,
            )
        return self._request_note_content(
            conversation_id=conversation_id,
            name=name,
            user_message=user_message,
        )

    def _complete_pending_note_selection(
        self,
        *,
        pending: PendingInteraction,
        message: str,
        conversation_id: str,
        user_message: str,
    ) -> ResponseSource | None:
        if is_rejection_message(message):
            pending_interactions.clear(conversation_id)
            return confirmation_source(
                user_message=user_message,
                facts="Note lookup cancelled.",
                conversation_id=conversation_id,
            )

        matches = list(pending.payload.get("matches", []))
        selected = self._selected_note_payload(message, matches)
        if selected is None:
            names = ", ".join(str(match.get("name", "")) for match in matches)
            return follow_up_source(
                user_message=user_message,
                facts=f"Specify one of these notes: {names}.",
                conversation_id=conversation_id,
            )

        pending_interactions.clear(conversation_id)
        return tool_result_source(
            user_message=user_message,
            facts=f"I found note {selected['name']}: {selected['content']}",
            tool_name="list_notes",
            conversation_id=conversation_id,
        )

    def _cancel_pending_note(self, *, conversation_id: str, user_message: str) -> ResponseSource:
        pending_interactions.clear(conversation_id)
        activity.standby(
            title=CANCELLED_NOTE_TITLE,
            detail=NO_NOTE_SAVED_DETAIL,
            source="assistant.flows.note",
        )
        return confirmation_source(
            user_message=user_message,
            facts="Note cancelled.",
            conversation_id=conversation_id,
        )
