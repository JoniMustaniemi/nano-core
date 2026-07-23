from __future__ import annotations

from typing import Any

from app.assistant.agent_rules import is_note_lookup_request, note_keywords_from_message
from app.assistant.pending import pending_interactions
from app.assistant.response_source import ResponseSource, follow_up_source, tool_result_source
from app.memory import repository


class NoteLookupMixin:
    """Note search and selection helpers."""

    def _lookup_notes_for_message(
        self,
        *,
        conversation_id: str,
        message: str,
        user_message: str,
    ) -> ResponseSource | None:
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
        matches = []
        for note in repository.list_notes():
            haystack = f"{note.name} {note.content}".lower()
            if any(keyword in haystack for keyword in keywords):
                matches.append(note)
        return matches

    def _format_note_match(self, note: Any) -> str:
        return f"I found note {note.name}: {note.content}"

    def _selected_note_payload(
        self,
        message: str,
        matches: list[Any],
    ) -> dict[str, Any] | None:
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
