from datetime import UTC, datetime

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

from app.config import get_settings
from app.duration import humanize_duration_seconds
from app.health import HealthCheckResult, run_health_checks
from app.memory import repository
from app.memory.repository import COUNTDOWN_KIND, delete_timer, get_timer, list_due_timers
from app.proactive.background_tick import check_presence_timeouts, run_proactive_background_tick
from app.runtime.activity import activity
from app.runtime.status_copy import HEALTH_ISSUE_DETECTED_TITLE

scheduler = BackgroundScheduler(daemon=True)

_LAST_HEALTH_STATUS: dict[str, bool] = {}
_TIMER_JOB_PREFIX = "timer:"


def _timer_job_id(timer_id: int) -> str:
    return f"{_TIMER_JOB_PREFIX}{timer_id}"


def complete_timer(timer_id: int) -> None:
    """
    Announce and remove a timer when it expires.

    Args:
        timer_id: Timer id value.

    Returns:
        None.
    """
    timer = get_timer(timer_id)
    if timer is None:
        unschedule_timer(timer_id)
        return

    if timer.kind != COUNTDOWN_KIND or timer.due_at is None:
        unschedule_timer(timer_id)
        return

    due_at = timer.due_at
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=UTC)
    now = datetime.now(UTC)
    if due_at > now:
        schedule_timer(timer_id, due_at)
        return

    title, detail = _format_due_timer(timer.label, timer.created_at, timer.due_at)
    activity.log(title=title, detail=detail, source="scheduler.timers")
    activity.announce_voice(detail)
    delete_timer(timer_id)
    unschedule_timer(timer_id)


def schedule_timer(timer_id: int, due_at: datetime | None) -> None:
    """
    Schedule a one-shot job to complete a timer at its due time.

    Args:
        timer_id: Timer id value.
        due_at: Timer due timestamp.

    Returns:
        None.
    """
    if due_at is None:
        unschedule_timer(timer_id)
        return
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=UTC)
    run_at = max(due_at, datetime.now(UTC))
    scheduler.add_job(
        complete_timer,
        trigger=DateTrigger(run_date=run_at),
        args=[timer_id],
        id=_timer_job_id(timer_id),
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=60,
    )


def unschedule_timer(timer_id: int) -> None:
    """
    Remove a scheduled timer completion job.

    Args:
        timer_id: Timer id value.

    Returns:
        None.
    """
    try:
        scheduler.remove_job(_timer_job_id(timer_id))
    except JobLookupError:
        return


def sync_timer_schedules() -> None:
    """
    Schedule completion jobs for all active countdown timers.

    Returns:
        None.
    """
    for timer in repository.list_countdown_timers():
        if timer.id is not None and timer.due_at is not None:
            schedule_timer(timer.id, timer.due_at)


def check_due_timers() -> None:
    """
    Check due timers as a fallback when a scheduled job was missed.

    Returns:
        None.
    """

    timers = list_due_timers(datetime.now(UTC))

    for timer in timers:
        if timer.id is None:
            continue
        complete_timer(timer.id)


def _format_due_timer(label: str, created_at: datetime, due_at: datetime) -> tuple[str, str]:
    """
    Format due timer.

    Args:
        label: Timer label.
        created_at: Timestamp when the record was created.
        due_at: Timer due timestamp.

    Returns:
        Tuple containing the requested values.
    """

    display_label = label.strip() or "Timer"

    duration_seconds = max(1, int((due_at - created_at).total_seconds()))

    label_suffix = "" if display_label == "Timer" else f" for {display_label}"

    return (
        "Timer complete.",
        f"Your {humanize_duration_seconds(duration_seconds)} timer{label_suffix} is complete.",
    )


def check_system_health() -> list[HealthCheckResult]:
    """
    Check system health.

    Returns:
        List of matching records or values.
    """

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
            title=HEALTH_ISSUE_DETECTED_TITLE,
            detail=f"{result.name}: {result.detail}",
            source="scheduler.health",
        )

        if previous is not False:
            message = f"I detected a problem with {result.name}. {result.detail}"
            activity.announce_voice(message)

    return results


def register_jobs() -> None:
    """
    Register jobs.

    Returns:
        None.
    """

    settings = get_settings()

    scheduler.add_job(
        check_due_timers,
        "interval",
        seconds=settings.timer_poll_interval_seconds,
        id="check_due_timers",
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

    scheduler.add_job(
        run_proactive_background_tick,
        "interval",
        seconds=settings.proactive_background_interval_seconds,
        id="run_proactive_background_tick",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        check_presence_timeouts,
        "interval",
        seconds=settings.presence_check_poll_interval_seconds,
        id="check_presence_timeouts",
        replace_existing=True,
        max_instances=1,
    )

    sync_timer_schedules()
