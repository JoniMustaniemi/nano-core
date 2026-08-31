from __future__ import annotations

from datetime import UTC, datetime

from app.memory.models import MeetingReminder


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def serialize_reminder(reminder: MeetingReminder) -> dict[str, str | int | bool | None]:
    start = _normalize_timestamp(reminder.start)
    end = _normalize_timestamp(reminder.end)
    remind_at = _normalize_timestamp(reminder.remind_at)
    created_at = _normalize_timestamp(reminder.created_at)
    updated_at = _normalize_timestamp(reminder.updated_at)
    fired_at = reminder.fired_at
    fired_at_str = _normalize_timestamp(fired_at).isoformat() if fired_at is not None else None

    return {
        "id": reminder.id,
        "calendar_id": reminder.calendar_id,
        "event_id": reminder.event_id,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "summary": reminder.summary,
        "all_day": reminder.all_day,
        "lead_minutes": reminder.lead_minutes,
        "remind_at": remind_at.isoformat(),
        "fired_at": fired_at_str,
        "created_at": created_at.isoformat(),
        "updated_at": updated_at.isoformat(),
    }
