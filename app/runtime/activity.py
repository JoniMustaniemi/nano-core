from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Literal

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
        self._lock = RLock()
        self._events: deque[ActivityEvent] = deque(maxlen=max_events)
        self._next_id = 1
        self._state: ActivityState = "standby"
        self._headline = "Nano is in standby."
        self._detail: str | None = None
        self._updated_at = datetime.now(UTC)
        self._record(
            kind="state",
            state="standby",
            source="system",
            title="Nano is in standby.",
            detail="Ready for the next task.",
        )

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
            self._next_id = 1
            self._state = "standby"
            self._headline = "Nano is in standby."
            self._detail = "Ready for the next task."
            self._updated_at = datetime.now(UTC)
            self._record(
                kind="state",
                state="standby",
                source="system",
                title="Nano is in standby.",
                detail="Ready for the next task.",
            )

    def standby(
        self,
        title: str = "Nano is in standby.",
        detail: str | None = None,
        source: str = "system",
    ) -> ActivityEvent:
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
        return self._record(
            kind="log",
            state=self._state,
            source=source,
            title=title,
            detail=detail,
        )

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "state": self._state,
                "headline": self._headline,
                "detail": self._detail,
                "updated_at": self._updated_at.isoformat(),
                "events": [event.to_dict() for event in self._events],
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
