from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings
from app.memory.repository import list_due_reminders, mark_reminder_sent
from app.runtime.activity import activity

scheduler = BackgroundScheduler()


def check_due_reminders() -> None:
    reminders = list_due_reminders(datetime.now(UTC))
    for reminder in reminders:
        if reminder.id is None:
            continue
        activity.log(
            title="Reminder due.",
            detail=reminder.content,
            source="scheduler.reminders",
        )
        mark_reminder_sent(reminder.id)


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
