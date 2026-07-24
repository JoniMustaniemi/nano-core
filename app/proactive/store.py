from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock

from app.proactive.types import ProactiveOffer


@dataclass
class ProactiveState:
    offer: ProactiveOffer | None = None
    internal_note_id: int | None = None
    presence_started_at: datetime | None = None
    waiting_for_presence: bool = False
    last_dismissal: str | None = None
    last_delivered_goal: str | None = None
    last_delivered_files: list[str] | None = None


class ProactiveStore:
    """In-memory store for the current proactive outreach session."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._state = ProactiveState()

    def set_offer(
        self,
        offer: ProactiveOffer,
        *,
        internal_note_id: int | None = None,
    ) -> None:
        with self._lock:
            self._state.offer = offer
            self._state.internal_note_id = internal_note_id

    def get_offer(self) -> ProactiveOffer | None:
        with self._lock:
            return self._state.offer

    def get_internal_note_id(self) -> int | None:
        with self._lock:
            return self._state.internal_note_id

    def has_offer(self) -> bool:
        with self._lock:
            return self._state.offer is not None

    def start_presence(self, *, started_at: datetime | None = None) -> None:
        with self._lock:
            self._state.waiting_for_presence = True
            self._state.presence_started_at = started_at or datetime.now(UTC)
            self._state.last_dismissal = None

    def clear_presence(self) -> None:
        with self._lock:
            self._state.waiting_for_presence = False
            self._state.presence_started_at = None

    def clear_offer(self) -> None:
        with self._lock:
            self._state.offer = None
            self._state.internal_note_id = None
            self._state.waiting_for_presence = False
            self._state.presence_started_at = None

    def set_last_goal(self, goal: str, *, files: list[str] | None = None) -> None:
        with self._lock:
            self._state.last_delivered_goal = goal
            self._state.last_delivered_files = list(files) if files else None

    def get_last_goal(self) -> str | None:
        with self._lock:
            return self._state.last_delivered_goal

    def get_last_files(self) -> list[str]:
        with self._lock:
            files = self._state.last_delivered_files
            return list(files) if files else []

    def clear_last_goal(self) -> None:
        with self._lock:
            self._state.last_delivered_goal = None
            self._state.last_delivered_files = None

    def set_dismissal(self, message: str) -> None:
        with self._lock:
            self._state.last_dismissal = message
            self._state.waiting_for_presence = False
            self._state.presence_started_at = None

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            offer = self._state.offer
            return {
                "waiting_for_presence": self._state.waiting_for_presence,
                "prompt": "Are you there?" if self._state.waiting_for_presence else None,
                "offer_kind": offer.kind if offer is not None else None,
                "dismissal": self._state.last_dismissal,
                "presence_started_at": (
                    self._state.presence_started_at.isoformat()
                    if self._state.presence_started_at is not None
                    else None
                ),
            }

    def reset(self) -> None:
        with self._lock:
            self._state = ProactiveState()


proactive_store = ProactiveStore()
