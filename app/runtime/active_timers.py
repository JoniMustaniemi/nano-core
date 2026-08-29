from __future__ import annotations

from datetime import UTC, datetime

from app.memory import repository
from app.memory.repository import COUNTDOWN_KIND, STOPWATCH_KIND


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def serialize_active_timers() -> list[dict[str, int | str]]:
    """
    Return active countdown timers for the activity snapshot.

    Returns:
        Serializable countdown timer records sorted by due time.
    """
    now = datetime.now(UTC)
    serialized: list[dict[str, int | str]] = []
    for timer in repository.list_countdown_timers():
        if timer.id is None:
            continue
        due_at = timer.due_at
        if due_at is None:
            continue
        due_at = _normalize_timestamp(due_at)
        started_at = _normalize_timestamp(timer.created_at)
        label = str(timer.label).strip() or "Timer"
        serialized.append(
            {
                "id": timer.id,
                "kind": COUNTDOWN_KIND,
                "label": label,
                "started_at": started_at.isoformat(),
                "due_at": due_at.isoformat(),
                "remaining_seconds": max(0, int((due_at - now).total_seconds())),
            }
        )
    return serialized


def serialize_active_stopwatches() -> list[dict[str, int | str]]:
    """
    Return active stopwatches for the activity snapshot.

    Returns:
        Serializable stopwatch records sorted by start time.
    """
    now = datetime.now(UTC)
    serialized: list[dict[str, int | str]] = []
    for stopwatch in repository.list_stopwatches():
        if stopwatch.id is None:
            continue
        started_at = _normalize_timestamp(stopwatch.created_at)
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
