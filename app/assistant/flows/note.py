from __future__ import annotations

from app.assistant.agent_rules import (
    is_note_add_request,
    is_note_list_request,
    note_content_from_message,
)
from app.assistant.flows.note_direct import NoteDirectMixin
from app.assistant.flows.note_lookup import NoteLookupMixin
from app.assistant.flows.note_pending import NotePendingMixin
from app.assistant.pending import pending_interactions
from app.assistant.response_source import ResponseSource


class NoteInteractionHandler(NoteDirectMixin, NoteLookupMixin, NotePendingMixin):
    """
    Handle note-specific direct requests and pending follow-ups.
    """

    def handle_direct_request(
        self,
        *,
        message: str,
        conversation_id: str,
        user_message: str,
    ) -> ResponseSource | None:
        """
        Handle direct note requests before the general planner runs.

        Args:
            message: User message or prompt text.
            conversation_id: Conversation identifier used to scope history and pending state.
            user_message: Original user message.

        Returns:
            Note response source when handled; otherwise None.
        """
        if is_note_list_request(message):
            pending_interactions.clear(conversation_id)
            return self._list_notes(
                conversation_id=conversation_id,
                user_message=user_message,
            )

        if is_note_add_request(message):
            note_content = note_content_from_message(message)
            return self._request_note_name(
                conversation_id=conversation_id,
                user_message=user_message,
                content=note_content,
            )

        return self._lookup_notes_for_message(
            conversation_id=conversation_id,
            message=message,
            user_message=user_message,
        )
