from __future__ import annotations

from datetime import datetime

ALLOWED_LEAD_MINUTES = frozenset({15, 30, 60})


class MeetingReminderValidationError(ValueError):
    pass


class MeetingReminderDatetimeError(ValueError):
    pass


def parse_iso_datetime(value: str, field_name: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MeetingReminderDatetimeError(
            f"Invalid {field_name}. Use an ISO-8601 datetime."
        ) from exc


def validate_upsert(
    *,
    all_day: bool,
    lead_minutes: int,
    start: datetime,
    now: datetime,
) -> None:
    if all_day:
        raise MeetingReminderValidationError("All-day events are not supported.")
    if lead_minutes not in ALLOWED_LEAD_MINUTES:
        raise MeetingReminderValidationError("lead_minutes must be one of: 15, 30, or 60.")
    if start <= now:
        raise MeetingReminderValidationError("start must be in the future.")
