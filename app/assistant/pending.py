from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

PendingKind = Literal[
    "note_content",
    "note_name",
    "note_selection",
    "timer_duration",
    "wipe_confirmation",
    "presence_check",
]


@dataclass(frozen=True, slots=True)
class PendingInteraction:
    conversation_id: str
    kind: PendingKind
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class PendingInteractionStore:
    def __init__(self) -> None:
        """
        Initialize the PendingInteractionStore instance.

        Returns:
            None.
        """
        self._items: dict[str, PendingInteraction] = {}

    def set(
        self,
        *,
        conversation_id: str,
        kind: PendingKind,
        payload: dict[str, Any] | None = None,
    ) -> PendingInteraction:
        """
        Set the requested operation.

        Args:
            conversation_id: Conversation identifier used to scope history and pending state.
            kind: Kind value.
            payload: Validated request payload.

        Returns:
            PendingInteraction result.
        """
        interaction = PendingInteraction(
            conversation_id=conversation_id,
            kind=kind,
            payload=payload or {},
        )
        self._items[conversation_id] = interaction
        return interaction

    def get(self, conversation_id: str) -> PendingInteraction | None:
        """
        Get the requested operation.

        Args:
            conversation_id: Conversation identifier used to scope history and pending state.

        Returns:
            Parsed value when available; otherwise None.
        """
        return self._items.get(conversation_id)

    def clear(self, conversation_id: str) -> None:
        """
        Clear the requested operation.

        Args:
            conversation_id: Conversation identifier used to scope history and pending state.

        Returns:
            None.
        """
        self._items.pop(conversation_id, None)

    def reset(self) -> None:
        """
        Reset the requested operation.

        Returns:
            None.
        """
        self._items.clear()


pending_interactions = PendingInteractionStore()
