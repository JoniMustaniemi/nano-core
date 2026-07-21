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
from app.assistant.response_source import (
    ResponseSource,
    confirmation_source,
    follow_up_source,
    tool_result_source,
)
from app.memory import repository
from app.runtime.activity import activity


class NoteInteractionHandler:
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

    def handle_pending(
        self,
        *,
        pending: PendingInteraction,
        message: str,
        conversation_id: str,
        user_message: str,
    ) -> ResponseSource | None:
        """
        Continue a pending note interaction.

        Args:
            pending: Pending interaction.
            message: User message or prompt text.
            conversation_id: Conversation identifier used to scope history and pending state.
            user_message: Original user message.

        Returns:
            Note response source when handled; otherwise None.
        """
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

    def _request_note_name(
        self,
        *,
        conversation_id: str,
        user_message: str,
        content: str | None = None,
    ) -> ResponseSource:
        """
        Ask for a note name before saving content.

        Args:
            conversation_id: Conversation identifier used to scope history.
            user_message: Original user message.
            content: Note content when it was provided inline.

        Returns:
            Follow-up response source.
        """
        payload = {"request": user_message}
        if content is not None:
            payload["content"] = content
        pending_interactions.set(
            conversation_id=conversation_id,
            kind="note_name",
            payload=payload,
        )
        activity.standby(
            title="Nano needs one detail.",
            detail="Waiting for the note name.",
            source="assistant.flows.note",
        )
        return follow_up_source(
            user_message=user_message,
            facts="What should I call this note?",
            conversation_id=conversation_id,
        )

    def _request_note_content(self, *, conversation_id: str, name: str, user_message: str) -> ResponseSource:
        """
        Ask for note content after a note name is known.

        Args:
            conversation_id: Conversation identifier used to scope history.
            name: Note name.
            user_message: Original user message.

        Returns:
            Follow-up response source.
        """
        pending_interactions.set(
            conversation_id=conversation_id,
            kind="note_content",
            payload={"name": name},
        )
        activity.standby(
            title="Nano needs one detail.",
            detail="Waiting for the note content.",
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
        """
        Save a named note, asking for missing pieces when needed.

        Args:
            conversation_id: Conversation identifier used to scope history.
            name: Note name.
            content: Note content.
            user_message: Original user message.

        Returns:
            Save confirmation or follow-up response source.
        """
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
            title="Nano is saving a note.",
            detail="Writing the note into local memory.",
            source="assistant.flows.note",
        )
        note = repository.add_note(cleaned, name=cleaned_name)
        pending_interactions.clear(conversation_id)
        activity.standby(
            title="Nano saved a note.",
            detail=f"Stored note #{note.id}.",
            source="assistant.flows.note",
        )
        return confirmation_source(
            user_message=user_message,
            facts=f"Saved note #{note.id}: {note.name}.",
            conversation_id=conversation_id,
        )

    def _list_notes(self, *, conversation_id: str, user_message: str) -> ResponseSource:
        """
        Return all saved notes in a factual format.

        Args:
            conversation_id: Conversation identifier used to scope history.
            user_message: Original user message.

        Returns:
            Notes summary response source.
        """
        notes = repository.list_notes()
        if not notes:
            facts = "I have no notes stored."
        else:
            note_lines = "\n".join(f"- {note.name}: {note.content}" for note in notes)
            facts = f"Here is what I remember:\n{note_lines}"
        activity.standby(
            title="Nano checked notes.",
            detail="Returned stored notes.",
            source="assistant.flows.note",
        )
        return tool_result_source(
            user_message=user_message,
            facts=facts,
            tool_name="list_notes",
            conversation_id=conversation_id,
        )

    def _lookup_notes_for_message(
        self,
        *,
        conversation_id: str,
        message: str,
        user_message: str,
    ) -> ResponseSource | None:
        """
        Search notes for keywords from a memory-shaped request.

        Args:
            conversation_id: Conversation identifier used to scope history.
            message: User message or prompt text.
            user_message: Original user message.

        Returns:
            Note lookup response source when handled; otherwise None.
        """
        if not is_note_lookup_request(message):
            return None

        keywords = note_keywords_from_message(message)
        if not keywords:
            return None

        matches = self._matching_notes(keywords)
        if not matches:
            return tool_result_source(
                user_message=user_message,
                facts=f"I found no notes matching {', '.join(keywords)}.",
                tool_name="list_notes",
                conversation_id=conversation_id,
            )

        if len(matches) == 1:
            return tool_result_source(
                user_message=user_message,
                facts=self._format_note_match(matches[0]),
                tool_name="list_notes",
                conversation_id=conversation_id,
            )

        candidate_lines = "\n".join(
            f"{index}. {note.name}" for index, note in enumerate(matches, start=1)
        )
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
        return follow_up_source(
            user_message=user_message,
            facts=f"I found multiple matching notes:\n{candidate_lines}\nWhich one?",
            conversation_id=conversation_id,
        )

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
        user_message: str,
    ) -> ResponseSource | None:
        """
        Complete a pending note content request.

        Args:
            message: User message or prompt text.
            conversation_id: Conversation identifier used to scope history.
            user_message: Original user message.

        Returns:
            Save confirmation, cancellation, or follow-up response source.
        """
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
        """
        Complete a pending note name request.

        Args:
            pending: Pending interaction.
            message: User message or prompt text.
            conversation_id: Conversation identifier used to scope history.
            user_message: Original user message.

        Returns:
            Save confirmation, cancellation, or follow-up response source.
        """
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
        """
        Complete a pending multiple-note selection.

        Args:
            pending: Pending interaction.
            message: User message or prompt text.
            conversation_id: Conversation identifier used to scope history.
            user_message: Original user message.

        Returns:
            Selected note response source, clarification, or cancellation.
        """
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

    def _cancel_pending_note(self, *, conversation_id: str, user_message: str) -> ResponseSource:
        """
        Cancel the current pending note interaction.

        Args:
            conversation_id: Conversation identifier used to scope history.
            user_message: Original user message.

        Returns:
            Cancellation response source.
        """
        pending_interactions.clear(conversation_id)
        activity.standby(
            title="Nano cancelled the note.",
            detail="No note was saved.",
            source="assistant.flows.note",
        )
        return confirmation_source(
            user_message=user_message,
            facts="Note cancelled.",
            conversation_id=conversation_id,
        )
