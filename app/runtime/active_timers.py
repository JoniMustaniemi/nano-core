from __future__ import annotations

from datetime import UTC, datetime

from app.memory import repository
from app.memory.repository import COUNTDOWN_KIND, STOPWATCH_KIND


def serialize_active_timers() -> list[dict[str, int | str]]:
    """
    Return active user timers and stopwatches for the activity snapshot.

    Returns:
        Serializable timer records sorted by start/due time.
    """
    now = datetime.now(UTC)
    timers = repository.list_timers()
    serialized: list[dict[str, int | str]] = []
    for timer in timers:
        if timer.id is None:
            continue
        label = str(timer.label).strip() or (
            "Stopwatch" if timer.kind == STOPWATCH_KIND else "Timer"
        )
        if timer.kind == STOPWATCH_KIND:
            started_at = timer.created_at
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=UTC)
            serialized.append(
                {
                    "id": timer.id,
                    "kind": STOPWATCH_KIND,
                    "label": label,
                    "started_at": started_at.isoformat(),
                    "elapsed_seconds": max(0, int((now - started_at).total_seconds())),
                }
            )
            continue

        due_at = timer.due_at
        if due_at is None:
            continue
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=UTC)
        serialized.append(
            {
                "id": timer.id,
                "kind": COUNTDOWN_KIND,
                "label": label,
                "due_at": due_at.isoformat(),
                "remaining_seconds": max(0, int((due_at - now).total_seconds())),
            }
        )
    return serialized
