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
    choose_standby_greeting,
)

ActivityState = Literal["standby", "working", "error"]
EventKind = Literal["state", "action", "log"]

VOICE_ANNOUNCE_SOURCE = "runtime.voice.announce"


@dataclass(frozen=True, slots=True)
class TaskTimer:
    label: str
    started_at: str
    expected_seconds: int

    def to_dict(self) -> dict[str, str | int]:
        return {
            "label": self.label,
            "started_at": self.started_at,
            "expected_seconds": self.expected_seconds,
        }


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
        self._task_timer: TaskTimer | None = None
        self._working_source: str | None = None
        self._last_voice_announcement: str | None = None
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
            self._task_timer = None
            self._working_source = None
            self._last_voice_announcement = None
            self._record(
                kind="state",
                state="standby",
                source="system",
                title=STANDBY_TITLE,
                detail=STANDBY_DETAIL_READY,
            )

    def start_task_timer(self, label: str, expected_seconds: int) -> None:
        with self._lock:
            self._task_timer = TaskTimer(
                label=label,
                started_at=datetime.now(UTC).isoformat(),
                expected_seconds=expected_seconds,
            )
        self.log(title=label, source="runtime.task_timer")

    def clear_task_timer(self) -> None:
        with self._lock:
            self._task_timer = None

    def release_to_idle(self, source: str = "system") -> ActivityEvent:
        """
        Return to standby after errors or aborted work.

        Args:
            source: Activity source label.

        Returns:
            Recorded standby activity event.
        """
        return self.standby(
            title=choose_standby_greeting(),
            detail=STANDBY_DETAIL_DEFAULT,
            source=source,
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
        with self._lock:
            self._task_timer = None
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
        with self._lock:
            self._task_timer = None
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

    def announce_voice(self, message: str) -> ActivityEvent | None:
        """
        Announce a spoken status line on configured playback targets.

        Duplicate messages are ignored until a different line is announced.

        Args:
            message: Message suitable for voice playback.

        Returns:
            ActivityEvent when queued for browser playback, otherwise None.
        """
        spoken = message.strip().rstrip(".")
        if not spoken:
            return None
        normalized = _normalize_voice_announcement(spoken)
        with self._lock:
            if normalized == self._last_voice_announcement:
                return None
            self._last_voice_announcement = normalized

        from app.config import get_settings
        from app.voice.service import GladosVoiceService

        settings = get_settings()
        if settings.voice_playback_mode in {"local", "both"}:
            try:
                GladosVoiceService().announce(spoken)
            except Exception:
                pass

        if settings.voice_playback_mode in {"browser", "both"}:
            return self.log(title=spoken, detail=spoken, source=VOICE_ANNOUNCE_SOURCE)
        return None

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            task_timer = self._task_timer.to_dict() if self._task_timer is not None else None
            return {
                "state": self._state,
                "headline": self._headline,
                "detail": self._detail,
                "working_source": self._working_source,
                "updated_at": self._updated_at.isoformat(),
                "task_timer": task_timer,
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
            if state == "working":
                self._working_source = source
            elif state in {"standby", "error"}:
                self._working_source = None
            self._updated_at = datetime.now(UTC)
            return event


def _normalize_voice_announcement(message: str) -> str:
    lowered = message.strip().rstrip(".").lower()
    skip = frozenset({"the", "a"})
    return " ".join(word for word in lowered.split() if word not in skip)


activity = ActivityHub()
