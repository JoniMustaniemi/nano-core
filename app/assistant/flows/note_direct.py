from __future__ import annotations

from app.assistant.pending import pending_interactions
from app.assistant.response_source import (
    ResponseSource,
    confirmation_source,
    follow_up_source,
    tool_result_source,
)
from app.memory import repository
from app.runtime.activity import activity
from app.runtime.status_copy import (
    CHECKED_NOTES_TITLE,
    NEEDS_DETAIL_TITLE,
    RETURNED_NOTES_DETAIL,
    SAVED_NOTE_DETAIL,
    SAVED_NOTE_TITLE,
    SAVING_NOTE_DETAIL,
    SAVING_NOTE_TITLE,
    WAITING_NOTE_CONTENT_DETAIL,
    WAITING_NOTE_NAME_DETAIL,
)


class NoteDirectMixin:
    """Direct note add/list operations."""

    def _request_note_name(
        self,
        *,
        conversation_id: str,
        user_message: str,
        content: str | None = None,
    ) -> ResponseSource:
        payload = {"request": user_message}
        if content is not None:
            payload["content"] = content
        pending_interactions.set(
            conversation_id=conversation_id,
            kind="note_name",
            payload=payload,
        )
        activity.standby(
            title=NEEDS_DETAIL_TITLE,
            detail=WAITING_NOTE_NAME_DETAIL,
            source="assistant.flows.note",
        )
        return follow_up_source(
            user_message=user_message,
            facts="What should I call this note?",
            conversation_id=conversation_id,
        )

    def _request_note_content(self, *, conversation_id: str, name: str, user_message: str) -> ResponseSource:
        pending_interactions.set(
            conversation_id=conversation_id,
            kind="note_content",
            payload={"name": name},
        )
        activity.standby(
            title=NEEDS_DETAIL_TITLE,
            detail=WAITING_NOTE_CONTENT_DETAIL,
            source="assistant.flows.note",
        )
        return follow_up_source(
            user_message=user_message,
            facts=f"What should I remember under {name}?",
            conversation_id=conversation_id,
        )

    def _save_note(
        self,
        *,
        conversation_id: str,
        name: str,
        content: str,
        user_message: str,
    ) -> ResponseSource:
        cleaned_name = name.strip()
        cleaned = content.strip()
        if not cleaned_name:
            return self._request_note_name(
                conversation_id=conversation_id,
                user_message=user_message,
                content=cleaned or None,
            )
        if not cleaned:
            return self._request_note_content(
                conversation_id=conversation_id,
                name=cleaned_name,
                user_message=user_message,
            )

        activity.working(
            title=SAVING_NOTE_TITLE,
            detail=SAVING_NOTE_DETAIL,
            source="assistant.flows.note",
        )
        note = repository.add_note(cleaned, name=cleaned_name)
        pending_interactions.clear(conversation_id)
        activity.standby(
            title=SAVED_NOTE_TITLE,
            detail=SAVED_NOTE_DETAIL,
            source="assistant.flows.note",
        )
        return confirmation_source(
            user_message=user_message,
            facts=f"Saved note #{note.id}: {note.name}.",
            conversation_id=conversation_id,
        )

    def _list_notes(self, *, conversation_id: str, user_message: str) -> ResponseSource:
        notes = repository.list_notes()
        if not notes:
            facts = "I have no notes stored."
        else:
            note_lines = "\n".join(f"- {note.name}: {note.content}" for note in notes)
            facts = f"Here is what I remember:\n{note_lines}"
        activity.standby(
            title=CHECKED_NOTES_TITLE,
            detail=RETURNED_NOTES_DETAIL,
            source="assistant.flows.note",
        )
        return tool_result_source(
            user_message=user_message,
            facts=facts,
            tool_name="list_notes",
            conversation_id=conversation_id,
        )
