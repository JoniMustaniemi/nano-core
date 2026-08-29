from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.duration import duration_seconds_from_tool_args, humanize_duration_seconds
from app.memory import repository
from app.memory.models import Timer
from app.runtime.activity import activity
from app.runtime.status_copy import STOPWATCH_STARTED_MESSAGE
from app.scheduler.jobs import schedule_timer, unschedule_timer
from app.tools.base import ToolSpec
from app.tools.errors import ToolError
from app.tools.registry import register_tool


def _start_timer(args: dict[str, Any]) -> str:
    """
    Start timer.

    Args:
        args: Tool argument dictionary.

    Returns:
        Generated or formatted string value.
    """
    duration_seconds = _resolve_duration_seconds(args)
    if duration_seconds <= 0:
        raise ToolError("Timer duration is required. Ask the user how long the timer should run.")

    label = str(args.get("label", "")).strip() or "Timer"
    due_at = datetime.now(UTC) + timedelta(seconds=duration_seconds)
    timer = repository.add_timer(label, due_at)
    if timer.id is not None:
        schedule_timer(timer.id, due_at)
    return (
        f"started timer {timer.id}: {label} "
        f"for {duration_seconds} seconds, due at {due_at.isoformat()}"
    )


def _start_stopwatch(args: dict[str, Any]) -> str:
    """
    Start stopwatch.

    Args:
        args: Tool argument dictionary.

    Returns:
        Generated or formatted string value.
    """
    label = str(args.get("label", "")).strip() or "Stopwatch"
    repository.add_stopwatch(label)
    activity.log(
        title=STOPWATCH_STARTED_MESSAGE,
        detail=label,
        source="assistant.flows.timer",
    )
    return STOPWATCH_STARTED_MESSAGE


def _resolve_duration_seconds(args: dict[str, Any]) -> int:
    """
    Resolve duration seconds.

    Args:
        args: Tool argument dictionary.

    Returns:
        Computed integer value.
    """
    return duration_seconds_from_tool_args(args)


def _list_timers(args: dict[str, Any]) -> str:
    """
    List timers.

    Args:
        args: Tool argument dictionary.

    Returns:
        Generated or formatted string value.
    """
    del args
    countdown_timers = _active_countdown_timers()
    stopwatches = _active_stopwatches()
    if not countdown_timers and not stopwatches:
        return "No active timers."

    now = datetime.now(UTC)
    lines: list[str] = []
    for timer in countdown_timers:
        lines.append(_format_countdown_timer(timer.label, timer.due_at, now))
    for stopwatch in stopwatches:
        lines.append(_format_stopwatch(stopwatch.label, stopwatch.created_at, now))

    total = len(lines)
    if total == 1:
        return f"You have one timer active. {lines[0]}"
    return f"You have {total} timers active:\n" + "\n".join(lines)


def _cancel_timers(args: dict[str, Any]) -> str:
    """
    Cancel timers.

    Args:
        args: Tool argument dictionary.

    Returns:
        Generated or formatted string value.
    """
    timer_id = args.get("timer_id")
    label = str(args.get("label", "")).strip().lower()
    timers = _active_countdown_timers()
    selected = [
        timer
        for timer in timers
        if _timer_matches_cancel_request(timer.id, timer.label, timer_id, label)
    ]

    if not selected:
        if timers:
            return "No matching active timers to cancel."
        return "No active timers to cancel."

    labels: list[str] = []
    for timer in selected:
        if timer.id is not None:
            unschedule_timer(timer.id)
            repository.delete_timer(timer.id)
        labels.append(timer.label)

    count = len(selected)
    noun = "timer" if count == 1 else "timers"
    if count == 1:
        return f"Cancelled 1 {noun}."
    return f"Cancelled {count} {noun}: {', '.join(labels)}."


def _clear_all_timers(args: dict[str, Any]) -> str:
    """
    Clear all active countdown timers and stopwatches.

    Args:
        args: Tool argument dictionary.

    Returns:
        Generated or formatted string value.
    """
    del args
    countdown_timers = _active_countdown_timers()
    stopwatches = _active_stopwatches()
    if not countdown_timers and not stopwatches:
        return "No active timers."

    for timer in countdown_timers:
        if timer.id is not None:
            unschedule_timer(timer.id)
            repository.delete_timer(timer.id)

    for stopwatch in stopwatches:
        if stopwatch.id is not None:
            repository.delete_timer(stopwatch.id)

    if stopwatches:
        activity.log(
            title="Stopwatch stopped.",
            detail="",
            source="assistant.flows.timer",
        )

    parts: list[str] = []
    countdown_count = len(countdown_timers)
    stopwatch_count = len(stopwatches)
    if countdown_count:
        noun = "countdown timer" if countdown_count == 1 else "countdown timers"
        parts.append(f"{countdown_count} {noun}")
    if stopwatch_count:
        noun = "stopwatch" if stopwatch_count == 1 else "stopwatches"
        parts.append(f"{stopwatch_count} {noun}")
    return f"Cleared {' and '.join(parts)}."


def _stop_stopwatches(args: dict[str, Any]) -> str:
    """
    Stop active stopwatches.

    Args:
        args: Tool argument dictionary.

    Returns:
        Generated or formatted string value.
    """
    stopwatch_id = args.get("stopwatch_id")
    label = str(args.get("label", "")).strip().lower()
    stopwatches = _active_stopwatches()
    selected = [
        stopwatch
        for stopwatch in stopwatches
        if _timer_matches_cancel_request(stopwatch.id, stopwatch.label, stopwatch_id, label)
    ]

    if not selected:
        if stopwatches:
            return "No matching active stopwatches to stop."
        return "No active stopwatches."

    for stopwatch in selected:
        if stopwatch.id is not None:
            repository.delete_timer(stopwatch.id)

    activity.log(
        title="Stopwatch stopped.",
        detail="",
        source="assistant.flows.timer",
    )

    count = len(selected)
    if count == 1:
        return "Stopped 1 stopwatch."
    return f"Stopped {count} stopwatches."


def _active_countdown_timers() -> list[Timer]:
    """
    Return active countdown timers.

    Returns:
        List of matching records or values.
    """
    return sorted(
        repository.list_countdown_timers(), key=lambda timer: timer.due_at or datetime.min
    )


def _active_stopwatches() -> list[Timer]:
    """
    Return active stopwatches.

    Returns:
        List of matching records or values.
    """
    return repository.list_stopwatches()


def _timer_matches_cancel_request(
    timer_id: int | None,
    timer_label: str,
    requested_id: Any,
    requested_label: str,
) -> bool:
    """
    Return whether an active timer matches a cancel request.

    Args:
        timer_id: Timer id value.
        timer_label: Timer label value.
        requested_id: Requested id value.
        requested_label: Requested label value.

    Returns:
        True when the condition is met; otherwise false.
    """
    if requested_id in (None, "") and not requested_label:
        return True
    if requested_id not in (None, ""):
        try:
            if timer_id == int(requested_id):
                return True
        except (TypeError, ValueError):
            return False
    return bool(requested_label and timer_label.lower() == requested_label)


def _format_countdown_timer(
    label: str,
    due_at: datetime | None,
    now: datetime,
) -> str:
    """
    Format active countdown timer.

    Args:
        label: Timer label.
        due_at: Timer due timestamp.
        now: Current timestamp used for time-based filtering.

    Returns:
        Generated or formatted string value.
    """
    if due_at is None:
        return f"{label} countdown is active."
    remaining = _timer_remaining_text(due_at, now)
    return f"{label} has {remaining} remaining."


def _format_stopwatch(
    label: str,
    started_at: datetime,
    now: datetime,
) -> str:
    """
    Format active stopwatch.

    Args:
        label: Stopwatch label.
        started_at: Stopwatch start timestamp.
        now: Current timestamp used for time-based filtering.

    Returns:
        Generated or formatted string value.
    """
    elapsed = _timer_elapsed_text(started_at, now)
    return f"{label} stopwatch has been running for {elapsed}."


def _timer_remaining_text(due_at: datetime, now: datetime) -> str:
    """
    Format the remaining time for an active timer.

    Args:
        due_at: Timer due timestamp.
        now: Current timestamp used for time-based filtering.

    Returns:
        Generated or formatted string value.
    """
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=UTC)
    remaining_seconds = max(0, int((due_at - now).total_seconds()))
    return humanize_duration_seconds(remaining_seconds)


def _timer_elapsed_text(started_at: datetime, now: datetime) -> str:
    """
    Format elapsed time for an active stopwatch.

    Args:
        started_at: Stopwatch start timestamp.
        now: Current timestamp used for time-based filtering.

    Returns:
        Generated or formatted string value.
    """
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    elapsed_seconds = max(0, int((now - started_at).total_seconds()))
    return humanize_duration_seconds(elapsed_seconds)


register_tool(
    ToolSpec(
        name="start_timer",
        description=(
            "start or add a timer for a specific duration; use this only when the user has "
            "given an explicit time length."
        ),
        args_schema={
            "duration_seconds": "Length of the timer in seconds.",
            "duration_minutes": "Optional length of the timer in minutes.",
            "duration_hours": "Optional length of the timer in hours.",
            "duration_text": "Optional natural duration like 30s or 2min.",
            "label": "Optional short timer label.",
        },
        handler=_start_timer,
        announcement="Starting a timer.",
        keywords=("timer", "countdown", "add timer", "start timer", "set timer"),
        ui_label="Add timer",
        ui_message="Add a timer.",
        ui_category="Timers",
        ui_description="Start or add a countdown timer.",
    )
)

register_tool(
    ToolSpec(
        name="start_stopwatch",
        description="start a stopwatch that counts up until stopped.",
        args_schema={
            "label": "Optional short stopwatch label.",
        },
        handler=_start_stopwatch,
        announcement="Starting a stopwatch.",
        keywords=("stopwatch", "stop watch", "start stopwatch", "add stopwatch"),
        ui_label="Start stopwatch",
        ui_message="Start a stopwatch.",
        ui_category="Timers",
        ui_description="Start a count-up stopwatch.",
    )
)

register_tool(
    ToolSpec(
        name="list_timers",
        description="list timers and stopwatches that have been created through the timer tools.",
        args_schema={},
        handler=_list_timers,
        announcement="Checking timers.",
        keywords=("timer", "timers", "stopwatch", "stopwatches"),
    )
)

register_tool(
    ToolSpec(
        name="cancel_timers",
        description="cancel active countdown timers that were created through the timer tool.",
        args_schema={
            "timer_id": "Optional timer id to cancel. If omitted, cancel all active timers.",
            "label": "Optional timer label to cancel. If omitted, cancel all active timers.",
        },
        handler=_cancel_timers,
        announcement="Cancelling timers.",
        keywords=("timer", "timers", "countdown"),
        ui_label="Cancel timers",
        ui_message="Cancel timers.",
        ui_category="Timers",
        ui_description="Stop active countdown timers.",
    )
)

register_tool(
    ToolSpec(
        name="stop_stopwatches",
        description="stop active stopwatches that were created through the stopwatch tool.",
        args_schema={
            "stopwatch_id": "Optional stopwatch id to stop. If omitted, stop all active stopwatches.",
            "label": "Optional stopwatch label to stop. If omitted, stop all active stopwatches.",
        },
        handler=_stop_stopwatches,
        announcement="Stopping stopwatches.",
        keywords=("stopwatch", "stopwatches", "stop watch"),
        ui_label="Stop stopwatch",
        ui_message="Stop stopwatch.",
        ui_category="Timers",
        ui_description="Stop active stopwatches.",
    )
)

register_tool(
    ToolSpec(
        name="clear_all_timers",
        description=(
            "clear all active countdown timers and stopwatches created through the timer tools."
        ),
        args_schema={},
        handler=_clear_all_timers,
        announcement="Clearing all timers.",
        keywords=("timer", "timers", "clear all timers", "delete all timers"),
        ui_label="Clear all timers",
        ui_message="Clear all timers.",
        ui_category="Timers",
        ui_description="Remove every active countdown timer and stopwatch.",
    )
)
