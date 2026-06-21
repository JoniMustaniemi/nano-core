from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

PendingKind = Literal["timer_duration", "wipe_confirmation"]


@dataclass(frozen=True, slots=True)
class PendingInteraction:
    conversation_id: str
    kind: PendingKind
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class PendingInteractionStore:
    def __init__(self) -> None:
        self._items: dict[str, PendingInteraction] = {}

    def set(
        self,
        *,
        conversation_id: str,
        kind: PendingKind,
        payload: dict[str, Any] | None = None,
    ) -> PendingInteraction:
        interaction = PendingInteraction(
            conversation_id=conversation_id,
            kind=kind,
            payload=payload or {},
        )
        self._items[conversation_id] = interaction
        return interaction

    def get(self, conversation_id: str) -> PendingInteraction | None:
        return self._items.get(conversation_id)

    def clear(self, conversation_id: str) -> None:
        self._items.pop(conversation_id, None)

    def reset(self) -> None:
        self._items.clear()


pending_interactions = PendingInteractionStore()
