from __future__ import annotations

from typing import Any

from app.assistant.agent_rules import (
    is_note_add_request,
    is_note_list_request,
    is_note_lookup_request,
    is_rejection_message,
    note_content_from_message,
    note_keywords_from_message,
)
from app.assistant.pending import PendingInteraction, pending_interactions
from app.memory import repository
from app.runtime.activity import activity


class NoteInteractionHandler:
    """
    Handle note-specific direct requests and pending follow-ups.
    """

    def handle_direct_request(self, *, message: str, conversation_id: str) -> str | None:
        """
        Handle direct note requests before the general planner runs.

        Args:
            message: User message or prompt text.
            conversation_id: Conversation identifier used to scope history and pending state.

        Returns:
            Note response when handled; otherwise None.
        """
        if is_note_list_request(message):
            pending_interactions.clear(conversation_id)
            return self._list_notes(conversation_id=conversation_id)

        if is_note_add_request(message):
            note_content = note_content_from_message(message)
            return self._request_note_name(
                conversation_id=conversation_id,
                message=message,
                content=note_content,
            )

        return self._lookup_notes_for_message(
            conversation_id=conversation_id,
            message=message,
        )

    def handle_pending(
        self,
        *,
        pending: PendingInteraction,
        message: str,
        conversation_id: str,
    ) -> str | None:
        """
        Continue a pending note interaction.

        Args:
            pending: Pending interaction.
            message: User message or prompt text.
            conversation_id: Conversation identifier used to scope history and pending state.

        Returns:
            Note response when handled; otherwise None.
        """
        if pending.kind == "note_content":
            return self._complete_pending_note_request(
                message=message,
                conversation_id=conversation_id,
            )

        if pending.kind == "note_name":
            return self._complete_pending_note_name(
                pending=pending,
                message=message,
                conversation_id=conversation_id,
            )

        if pending.kind == "note_selection":
            return self._complete_pending_note_selection(
                pending=pending,
                message=message,
                conversation_id=conversation_id,
            )

        return None

    def _request_note_name(
        self,
        *,
        conversation_id: str,
        message: str,
        content: str | None = None,
    ) -> str:
        """
        Ask for a note name before saving content.

        Args:
            conversation_id: Conversation identifier used to scope history.
            message: User message or prompt text.
            content: Note content when it was provided inline.

        Returns:
            Follow-up question.
        """
        follow_up = "What should I call this note?"
        payload = {"request": message}
        if content is not None:
            payload["content"] = content
        pending_interactions.set(
            conversation_id=conversation_id,
            kind="note_name",
            payload=payload,
        )
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=follow_up,
        )
        activity.standby(
            title="Nano needs one detail.",
            detail="Waiting for the note name.",
            source="assistant.flows.note",
        )
        return follow_up

    def _request_note_content(self, *, conversation_id: str, name: str) -> str:
        """
        Ask for note content after a note name is known.

        Args:
            conversation_id: Conversation identifier used to scope history.
            name: Note name.

        Returns:
            Follow-up question.
        """
        follow_up = f"What should I remember under {name}?"
        pending_interactions.set(
            conversation_id=conversation_id,
            kind="note_content",
            payload={"name": name},
        )
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=follow_up,
        )
        activity.standby(
            title="Nano needs one detail.",
            detail="Waiting for the note content.",
            source="assistant.flows.note",
        )
        return follow_up

    def _save_note(self, *, conversation_id: str, name: str, content: str) -> str:
        """
        Save a named note, asking for missing pieces when needed.

        Args:
            conversation_id: Conversation identifier used to scope history.
            name: Note name.
            content: Note content.

        Returns:
            Save confirmation or follow-up question.
        """
        cleaned_name = name.strip()
        cleaned = content.strip()
        if not cleaned_name:
            return self._request_note_name(
                conversation_id=conversation_id,
                message="Add a note.",
                content=cleaned or None,
            )
        if not cleaned:
            return self._request_note_content(
                conversation_id=conversation_id,
                name=cleaned_name,
            )

        activity.working(
            title="Nano is saving a note.",
            detail="Writing the note into local memory.",
            source="assistant.flows.note",
        )
        note = repository.add_note(cleaned, name=cleaned_name)
        pending_interactions.clear(conversation_id)
        response = f"Saved note #{note.id}: {note.name}."
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=response,
        )
        activity.standby(
            title="Nano saved a note.",
            detail=f"Stored note #{note.id}.",
            source="assistant.flows.note",
        )
        return response

    def _list_notes(self, *, conversation_id: str) -> str:
        """
        Return all saved notes in a user-facing format.

        Args:
            conversation_id: Conversation identifier used to scope history.

        Returns:
            Notes summary.
        """
        notes = repository.list_notes()
        if not notes:
            response = "I have no notes stored."
        else:
            note_lines = "\n".join(f"- {note.name}: {note.content}" for note in notes)
            response = f"Here is what I remember:\n{note_lines}"
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=response,
        )
        activity.standby(
            title="Nano checked notes.",
            detail="Returned stored notes.",
            source="assistant.flows.note",
        )
        return response

    def _lookup_notes_for_message(self, *, conversation_id: str, message: str) -> str | None:
        """
        Search notes for keywords from a memory-shaped request.

        Args:
            conversation_id: Conversation identifier used to scope history.
            message: User message or prompt text.

        Returns:
            Note lookup response when handled; otherwise None.
        """
        if not is_note_lookup_request(message):
            return None

        keywords = note_keywords_from_message(message)
        if not keywords:
            return None

        matches = self._matching_notes(keywords)
        if not matches:
            response = f"I found no notes matching {', '.join(keywords)}."
            repository.add_chat_message(
                conversation_id=conversation_id,
                role="assistant",
                content=response,
            )
            return response

        if len(matches) == 1:
            response = self._format_note_match(matches[0])
            repository.add_chat_message(
                conversation_id=conversation_id,
                role="assistant",
                content=response,
            )
            return response

        candidate_lines = "\n".join(
            f"{index}. {note.name}" for index, note in enumerate(matches, start=1)
        )
        response = f"I found multiple matching notes:\n{candidate_lines}\nWhich one?"
        pending_interactions.set(
            conversation_id=conversation_id,
            kind="note_selection",
            payload={
                "matches": [
                    {"id": note.id, "name": note.name, "content": note.content}
                    for note in matches
                ],
            },
        )
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=response,
        )
        return response

    def _matching_notes(self, keywords: list[str]) -> list[Any]:
        """
        Find notes whose name or content contains any keyword.

        Args:
            keywords: Search keywords.

        Returns:
            Matching note objects.
        """
        matches = []
        for note in repository.list_notes():
            haystack = f"{note.name} {note.content}".lower()
            if any(keyword in haystack for keyword in keywords):
                matches.append(note)
        return matches

    def _format_note_match(self, note: Any) -> str:
        """
        Format one matching note for the user.

        Args:
            note: Note-like object.

        Returns:
            User-facing note lookup result.
        """
        return f"I found note {note.name}: {note.content}"

    def _complete_pending_note_request(
        self,
        *,
        message: str,
        conversation_id: str,
    ) -> str | None:
        """
        Complete a pending note content request.

        Args:
            message: User message or prompt text.
            conversation_id: Conversation identifier used to scope history.

        Returns:
            Save confirmation, cancellation, or follow-up response.
        """
        if is_rejection_message(message):
            return self._cancel_pending_note(conversation_id=conversation_id)

        content = note_content_from_message(message) if is_note_add_request(message) else message
        pending = pending_interactions.get(conversation_id)
        name = str((pending.payload if pending else {}).get("name", "")).strip()
        return self._save_note(conversation_id=conversation_id, name=name, content=content)

    def _complete_pending_note_name(
        self,
        *,
        pending: PendingInteraction,
        message: str,
        conversation_id: str,
    ) -> str | None:
        """
        Complete a pending note name request.

        Args:
            pending: Pending interaction.
            message: User message or prompt text.
            conversation_id: Conversation identifier used to scope history.

        Returns:
            Save confirmation, cancellation, or follow-up response.
        """
        if is_rejection_message(message):
            return self._cancel_pending_note(conversation_id=conversation_id)

        name = message.strip()
        content = str(pending.payload.get("content", "")).strip()
        if content:
            return self._save_note(conversation_id=conversation_id, name=name, content=content)
        return self._request_note_content(conversation_id=conversation_id, name=name)

    def _complete_pending_note_selection(
        self,
        *,
        pending: PendingInteraction,
        message: str,
        conversation_id: str,
    ) -> str | None:
        """
        Complete a pending multiple-note selection.

        Args:
            pending: Pending interaction.
            message: User message or prompt text.
            conversation_id: Conversation identifier used to scope history.

        Returns:
            Selected note response, clarification, or cancellation.
        """
        if is_rejection_message(message):
            pending_interactions.clear(conversation_id)
            response = "Note lookup cancelled."
            repository.add_chat_message(
                conversation_id=conversation_id,
                role="assistant",
                content=response,
            )
            return response

        matches = list(pending.payload.get("matches", []))
        selected = self._selected_note_payload(message, matches)
        if selected is None:
            names = ", ".join(str(match.get("name", "")) for match in matches)
            response = f"Specify one of these notes: {names}."
            repository.add_chat_message(
                conversation_id=conversation_id,
                role="assistant",
                content=response,
            )
            return response

        pending_interactions.clear(conversation_id)
        response = f"I found note {selected['name']}: {selected['content']}"
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=response,
        )
        return response

    def _selected_note_payload(
        self,
        message: str,
        matches: list[Any],
    ) -> dict[str, Any] | None:
        """
        Resolve a note selection by number or note name.

        Args:
            message: User message or prompt text.
            matches: Candidate note payloads.

        Returns:
            Selected note payload when recognized; otherwise None.
        """
        lowered = message.strip().lower()
        if lowered.isdigit():
            index = int(lowered) - 1
            if 0 <= index < len(matches):
                return dict(matches[index])
        for match in matches:
            name = str(match.get("name", "")).lower()
            if name and (lowered == name or lowered in name or name in lowered):
                return dict(match)
        return None

    def _cancel_pending_note(self, *, conversation_id: str) -> str:
        """
        Cancel the current pending note interaction.

        Args:
            conversation_id: Conversation identifier used to scope history.

        Returns:
            Cancellation response.
        """
        response = "Note cancelled."
        pending_interactions.clear(conversation_id)
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=response,
        )
        activity.standby(
            title="Nano cancelled the note.",
            detail="No note was saved.",
            source="assistant.flows.note",
        )
        return response
