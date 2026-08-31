from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.integrations.google_calendar.auth import get_calendar_service
from app.meeting_reminders.serialization import serialize_reminder
from app.meeting_reminders.validation import parse_iso_datetime, validate_upsert
from app.memory import meeting_reminders as reminder_repo
from app.runtime.activity import activity


def _schedule_reminder(reminder_id: str, remind_at: datetime) -> None:
    from app.scheduler.jobs import schedule_reminder

    schedule_reminder(reminder_id, remind_at)


def _unschedule_reminder(reminder_id: str) -> None:
    from app.scheduler.jobs import unschedule_reminder

    unschedule_reminder(reminder_id)


def ensure_calendar_connected() -> None:
    get_calendar_service()


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _compute_remind_at(start: datetime, lead_minutes: int) -> datetime:
    normalized_start = _normalize_timestamp(start)
    return normalized_start - timedelta(minutes=lead_minutes)


def upsert_meeting_reminder(
    *,
    calendar_id: str,
    event_id: str,
    start_raw: str,
    end_raw: str,
    summary: str,
    all_day: bool,
    lead_minutes: int,
) -> dict[str, str | int | bool | None]:
    now = datetime.now(UTC)
    start = _normalize_timestamp(parse_iso_datetime(start_raw, "start"))
    end = _normalize_timestamp(parse_iso_datetime(end_raw, "end"))
    validate_upsert(all_day=all_day, lead_minutes=lead_minutes, start=start, now=now)
    remind_at = _compute_remind_at(start, lead_minutes)

    reminder = reminder_repo.upsert_reminder(
        calendar_id=calendar_id,
        event_id=event_id,
        start=start,
        end=end,
        summary=summary,
        all_day=all_day,
        lead_minutes=lead_minutes,
        remind_at=remind_at,
    )
    _schedule_reminder(reminder.id, remind_at)
    return serialize_reminder(reminder)


def list_meeting_reminders() -> list[dict[str, str | int | bool | None]]:
    now = datetime.now(UTC)
    reminder_repo.prune_expired_reminders(now)
    reminders = reminder_repo.list_active_reminders(now)
    return [serialize_reminder(reminder) for reminder in reminders]


def delete_meeting_reminder(
    calendar_id: str,
    event_id: str,
    start_raw: str,
) -> None:
    start = _normalize_timestamp(parse_iso_datetime(start_raw, "start"))
    reminder = reminder_repo.delete_reminder_by_key(calendar_id, event_id, start)
    if reminder is not None:
        _unschedule_reminder(reminder.id)


def fire_reminder(reminder_id: str) -> None:
    reminder = reminder_repo.get_reminder(reminder_id)
    if reminder is None:
        _unschedule_reminder(reminder_id)
        return

    if reminder.fired_at is not None:
        _unschedule_reminder(reminder_id)
        return

    now = datetime.now(UTC)
    remind_at = _normalize_timestamp(reminder.remind_at)
    if remind_at > now:
        _schedule_reminder(reminder_id, remind_at)
        return

    summary = reminder.summary.strip() or "Meeting"
    title = "Meeting reminder"
    detail = f"Reminder: {summary} starts in {reminder.lead_minutes} minutes."
    activity.log(title=title, detail=detail, source="scheduler.meeting_reminders")
    activity.announce_voice(detail)
    reminder_repo.mark_reminder_fired(reminder_id, now)
    _unschedule_reminder(reminder_id)
