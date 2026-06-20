from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings
from app.memory.repository import list_due_reminders, mark_reminder_sent
from app.runtime.activity import activity

scheduler = BackgroundScheduler(daemon=True)


def check_due_reminders() -> None:
    reminders = list_due_reminders(datetime.now(UTC))
    for reminder in reminders:
        if reminder.id is None:
            continue
        title, detail = _format_due_reminder(reminder.content, reminder.created_at, reminder.due_at)
        activity.log(title=title, detail=detail, source="scheduler.reminders")
        mark_reminder_sent(reminder.id)


def _format_due_reminder(content: str, created_at: datetime, due_at: datetime) -> tuple[str, str]:
    if content.startswith("[timer] "):
        label = content.removeprefix("[timer] ").strip() or "Timer"
        duration_seconds = max(1, int((due_at - created_at).total_seconds()))
        return (
            "Timer complete.",
            f"Your {_humanize_duration(duration_seconds)} timer for {label} is complete.",
        )
    return "Reminder due.", content


def _humanize_duration(duration_seconds: int) -> str:
    if duration_seconds % 60 == 0:
        minutes = duration_seconds // 60
        if minutes == 1:
            return "1 minute"
        return f"{minutes} minutes"
    if duration_seconds == 1:
        return "1 second"
    return f"{duration_seconds} seconds"


def register_jobs() -> None:
    settings = get_settings()
    scheduler.add_job(
        check_due_reminders,
        "interval",
        seconds=settings.reminder_poll_interval_seconds,
        id="check_due_reminders",
        replace_existing=True,
        max_instances=1,
    )
