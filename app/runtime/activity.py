from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Literal

from app.runtime.status_copy import (
    STANDBY_DETAIL_DEFAULT,
    STANDBY_DETAIL_READY,
    STANDBY_TITLE,
)

ActivityState = Literal["standby", "working", "error"]
EventKind = Literal["state", "action", "log"]


@dataclass(frozen=True, slots=True)
class ActivityEvent:
    id: int
    kind: EventKind
    state: ActivityState
    source: str
    title: str
    detail: str | None
    created_at: str

    def to_dict(self) -> dict[str, str | int | None]:
        """
        Convert dict.

        Returns:
            Dictionary containing the requested data.
        """
        return {
            "id": self.id,
            "kind": self.kind,
            "state": self.state,
            "source": self.source,
            "title": self.title,
            "detail": self.detail,
            "created_at": self.created_at,
        }


class ActivityHub:
    def __init__(self, max_events: int = 100) -> None:
        """
        Initialize the ActivityHub instance.

        Args:
            max_events: Maximum number of activity events to retain.

        Returns:
            None.
        """
        self._lock = RLock()
        self._events: deque[ActivityEvent] = deque(maxlen=max_events)
        self._next_id = 1
        self._state: ActivityState = "standby"
        self._headline = STANDBY_TITLE
        self._detail: str | None = STANDBY_DETAIL_DEFAULT
        self._updated_at = datetime.now(UTC)
        self._record(
            kind="state",
            state="standby",
            source="system",
            title=STANDBY_TITLE,
            detail=STANDBY_DETAIL_DEFAULT,
        )

    def reset(self) -> None:
        """
        Reset the requested operation.

        Returns:
            None.
        """
        with self._lock:
            self._events.clear()
            self._next_id = 1
            self._state = "standby"
            self._headline = STANDBY_TITLE
            self._detail = STANDBY_DETAIL_DEFAULT
            self._updated_at = datetime.now(UTC)
            self._record(
                kind="state",
                state="standby",
                source="system",
                title=STANDBY_TITLE,
                detail=STANDBY_DETAIL_READY,
            )

    def standby(
        self,
        title: str = STANDBY_TITLE,
        detail: str | None = STANDBY_DETAIL_DEFAULT,
        source: str = "system",
    ) -> ActivityEvent:
        """
        Record standby activity for the requested operation.

        Args:
            title: Short error title to report.
            detail: Detailed error text to report.
            source: Source value.

        Returns:
            ActivityEvent result.
        """
        return self._record(
            kind="state",
            state="standby",
            source=source,
            title=title,
            detail=detail,
        )

    def working(
        self,
        title: str,
        detail: str | None = None,
        source: str = "system",
    ) -> ActivityEvent:
        """
        Handle working.

        Args:
            title: Short error title to report.
            detail: Detailed error text to report.
            source: Source value.

        Returns:
            ActivityEvent result.
        """
        return self._record(
            kind="state",
            state="working",
            source=source,
            title=title,
            detail=detail,
        )

    def error(
        self,
        title: str,
        detail: str | None = None,
        source: str = "system",
    ) -> ActivityEvent:
        """
        Handle error.

        Args:
            title: Short error title to report.
            detail: Detailed error text to report.
            source: Source value.

        Returns:
            ActivityEvent result.
        """
        return self._record(
            kind="state",
            state="error",
            source=source,
            title=title,
            detail=detail,
        )

    def log(
        self,
        title: str,
        detail: str | None = None,
        source: str = "system",
    ) -> ActivityEvent:
        """
        Log the requested operation.

        Args:
            title: Short error title to report.
            detail: Detailed error text to report.
            source: Source value.

        Returns:
            ActivityEvent result.
        """
        return self._record(
            kind="log",
            state=self._state,
            source=source,
            title=title,
            detail=detail,
        )

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            from app.assistant.pending import pending_interactions
            from app.config import get_settings
            from app.proactive.store import proactive_store

            settings = get_settings()
            pending = pending_interactions.get(settings.proactive_conversation_id)
            pending_kind = pending.kind if pending is not None else None

            return {
                "state": self._state,
                "headline": self._headline,
                "detail": self._detail,
                "updated_at": self._updated_at.isoformat(),
                "events": [event.to_dict() for event in self._events],
                "proactive": proactive_store.snapshot(),
                "pending": {"kind": pending_kind},
            }

    def _record(
        self,
        *,
        kind: EventKind,
        state: ActivityState,
        source: str,
        title: str,
        detail: str | None,
    ) -> ActivityEvent:
        """
        Handle record.

        Args:
            kind: Kind value.
            state: State value.
            source: Source value.
            title: Short error title to report.
            detail: Detailed error text to report.

        Returns:
            ActivityEvent result.
        """
        with self._lock:
            event = ActivityEvent(
                id=self._next_id,
                kind=kind,
                state=state,
                source=source,
                title=title,
                detail=detail,
                created_at=datetime.now(UTC).isoformat(),
            )
            self._next_id += 1
            self._events.append(event)
            self._state = state
            self._headline = title
            self._detail = detail
            self._updated_at = datetime.now(UTC)
            return event


activity = ActivityHub()
