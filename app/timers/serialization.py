from __future__ import annotations

from datetime import UTC, datetime

from app.memory import repository
from app.memory.models import Timer
from app.memory.repository import COUNTDOWN_KIND, STOPWATCH_KIND
from app.timers.clock import normalize_utc, resolve_stopwatch_started_at


def _serialize_countdown(timer: Timer) -> dict[str, int | str] | None:
    if timer.id is None:
        return None
    due_at = timer.due_at
    if due_at is None:
        return None
    duration_seconds = timer.duration_seconds
    if duration_seconds is None or duration_seconds <= 0:
        return None
    now = datetime.now(UTC)
    due_at = normalize_utc(due_at)
    started_at = resolve_stopwatch_started_at(timer.created_at, now=now)
    label = str(timer.label).strip() or "Timer"
    return {
        "id": timer.id,
        "kind": COUNTDOWN_KIND,
        "label": label,
        "duration_seconds": duration_seconds,
        "started_at": started_at.isoformat(),
        "due_at": due_at.isoformat(),
        "remaining_seconds": max(0, int((due_at - now).total_seconds())),
    }


def serialize_active_timers() -> list[dict[str, int | str]]:
    serialized: list[dict[str, int | str]] = []
    for timer in repository.list_countdown_timers():
        payload = _serialize_countdown(timer)
        if payload is not None:
            serialized.append(payload)
    return serialized


def serialize_active_stopwatches() -> list[dict[str, int | str]]:
    now = datetime.now(UTC)
    serialized: list[dict[str, int | str]] = []
    for stopwatch in repository.list_stopwatches():
        if stopwatch.id is None:
            continue
        started_at = resolve_stopwatch_started_at(stopwatch.created_at, now=now)
        label = str(stopwatch.label).strip() or "Stopwatch"
        serialized.append(
            {
                "id": stopwatch.id,
                "kind": STOPWATCH_KIND,
                "label": label,
                "started_at": started_at.isoformat(),
                "elapsed_seconds": max(0, int((now - started_at).total_seconds())),
            }
        )
    return serialized


def serialize_timer_by_id(timer_id: int) -> dict[str, int | str] | None:
    timer = repository.get_timer(timer_id)
    if timer is None or timer.kind != COUNTDOWN_KIND:
        return None
    return _serialize_countdown(timer)


def serialize_stopwatch_by_id(stopwatch_id: int) -> dict[str, int | str] | None:
    stopwatch = repository.get_timer(stopwatch_id)
    if stopwatch is None or stopwatch.kind != STOPWATCH_KIND or stopwatch.id is None:
        return None
    now = datetime.now(UTC)
    started_at = resolve_stopwatch_started_at(stopwatch.created_at, now=now)
    label = str(stopwatch.label).strip() or "Stopwatch"
    return {
        "id": stopwatch.id,
        "kind": STOPWATCH_KIND,
        "label": label,
        "started_at": started_at.isoformat(),
        "elapsed_seconds": max(0, int((now - started_at).total_seconds())),
    }
