from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings
from app.health import HealthCheckResult, run_health_checks
from app.memory.repository import delete_reminder, list_due_reminders, mark_reminder_sent
from app.runtime.activity import activity
from app.voice.service import GladosVoiceService, VoiceUnavailableError

scheduler = BackgroundScheduler(daemon=True)
_LAST_HEALTH_STATUS: dict[str, bool] = {}


def check_due_reminders() -> None:
    reminders = list_due_reminders(datetime.now(UTC))
    for reminder in reminders:
        if reminder.id is None:
            continue
        title, detail = _format_due_reminder(reminder.content, reminder.created_at, reminder.due_at)
        activity.log(title=title, detail=detail, source="scheduler.reminders")
        if reminder.content.startswith("[timer] "):
            _announce_timer_completion(detail)
            delete_reminder(reminder.id)
            continue
        mark_reminder_sent(reminder.id)


def _format_due_reminder(content: str, created_at: datetime, due_at: datetime) -> tuple[str, str]:
    if content.startswith("[timer] "):
        label = content.removeprefix("[timer] ").strip() or "Timer"
        duration_seconds = max(1, int((due_at - created_at).total_seconds()))
        label_suffix = "" if label == "Timer" else f" for {label}"
        return (
            "Timer complete.",
            f"Your {_humanize_duration(duration_seconds)} timer{label_suffix} is complete.",
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


def _announce_timer_completion(message: str) -> None:
    try:
        GladosVoiceService().announce(message)
    except VoiceUnavailableError:
        return


def check_system_health() -> list[HealthCheckResult]:
    results = run_health_checks()
    failing = [result for result in results if not result.ok]
    if not failing:
        for result in results:
            previous = _LAST_HEALTH_STATUS.get(result.name)
            _LAST_HEALTH_STATUS[result.name] = True
            if previous is False:
                activity.log(
                    title="Health check recovered.",
                    detail=f"{result.name}: {result.detail}",
                    source="scheduler.health",
                )
        return results

    for result in results:
        previous = _LAST_HEALTH_STATUS.get(result.name)
        _LAST_HEALTH_STATUS[result.name] = result.ok
        if result.ok:
            continue
        activity.error(
            title="Nano detected a health issue.",
            detail=f"{result.name}: {result.detail}",
            source="scheduler.health",
        )
        if previous is not False:
            _announce_health_issue(result)
    return results


def _announce_health_issue(result: HealthCheckResult) -> None:
    message = f"I detected a problem with {result.name}. {result.detail}"
    try:
        GladosVoiceService().announce(message)
    except VoiceUnavailableError:
        return


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
    scheduler.add_job(
        check_system_health,
        "interval",
        seconds=settings.health_check_interval_seconds,
        id="check_system_health",
        replace_existing=True,
        max_instances=1,
    )
