from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.duration import parse_duration_to_seconds
from app.memory import repository
from app.tools.base import ToolSpec
from app.tools.registry import register_tool


def _start_timer(args: dict[str, Any]) -> str:
    duration_seconds = _resolve_duration_seconds(args)
    if duration_seconds <= 0:
        return "Timer duration is required. Ask the user how long the timer should run."

    label = str(args.get("label", "")).strip() or "Timer"
    due_at = datetime.now(UTC) + timedelta(seconds=duration_seconds)
    reminder = repository.add_reminder(f"[timer] {label}", due_at)
    return (
        f"started timer {reminder.id}: {label} "
        f"for {duration_seconds} seconds, due at {due_at.isoformat()}"
    )


def _resolve_duration_seconds(args: dict[str, Any]) -> int:
    if "duration_seconds" in args:
        return int(args.get("duration_seconds", 0))
    if "duration_minutes" in args:
        return int(args.get("duration_minutes", 0)) * 60
    if "duration_hours" in args:
        return int(args.get("duration_hours", 0)) * 3600
    if "duration_text" in args:
        return _parse_duration_text(str(args.get("duration_text", "")))
    return 0


def _parse_duration_text(raw: str) -> int:
    return parse_duration_to_seconds(raw)


def _list_timers(args: dict[str, Any]) -> str:
    del args
    timers = _active_timer_reminders()
    if not timers:
        return "No active timers."

    now = datetime.now(UTC)
    if len(timers) == 1:
        timer = timers[0]
        label = _timer_label(timer.content)
        remaining = _timer_remaining_text(timer.due_at, now)
        if label == "Timer":
            return f"You have one timer active and it has {remaining} remaining."
        return f"You have one timer active. {label} has {remaining} remaining."

    count = len(timers)
    lines = [
        _format_active_timer(timer.content, timer.due_at, now)
        for timer in timers
    ]
    return f"You have {count} timers active:\n" + "\n".join(lines)


def _cancel_timers(args: dict[str, Any]) -> str:
    timer_id = args.get("timer_id")
    label = str(args.get("label", "")).strip().lower()
    timers = _active_timer_reminders()
    selected = [
        timer
        for timer in timers
        if _timer_matches_cancel_request(timer.id, timer.content, timer_id, label)
    ]

    if not selected:
        if timers:
            return "No matching active timers to cancel."
        return "No active timers to cancel."

    labels: list[str] = []
    for timer in selected:
        if timer.id is not None:
            repository.delete_reminder(timer.id)
        labels.append(_timer_label(timer.content))

    count = len(selected)
    noun = "timer" if count == 1 else "timers"
    return f"Cancelled {count} {noun}."


def _active_timer_reminders() -> list[Any]:
    reminders = repository.list_reminders()
    timers = [reminder for reminder in reminders if reminder.content.startswith("[timer] ")]
    return sorted(timers, key=lambda reminder: reminder.due_at)


def _timer_matches_cancel_request(
    timer_id: int | None,
    content: str,
    requested_id: Any,
    requested_label: str,
) -> bool:
    if requested_id in (None, "") and not requested_label:
        return True
    if requested_id not in (None, ""):
        try:
            if timer_id == int(requested_id):
                return True
        except (TypeError, ValueError):
            return False
    return bool(requested_label and _timer_label(content).lower() == requested_label)


def _format_active_timer(
    content: str,
    due_at: datetime,
    now: datetime,
) -> str:
    remaining = _timer_remaining_text(due_at, now)
    return f"{_timer_label(content)} has {remaining} remaining."


def _timer_remaining_text(due_at: datetime, now: datetime) -> str:
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=UTC)
    remaining_seconds = max(0, int((due_at - now).total_seconds()))
    return _humanize_remaining_time(remaining_seconds)


def _timer_label(content: str) -> str:
    return content.removeprefix("[timer] ").strip() or "Timer"


def _humanize_remaining_time(total_seconds: int) -> str:
    if total_seconds <= 0:
        return "less than a second"

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts: list[str] = []
    if hours:
        parts.append(_format_unit(hours, "hour"))
    if minutes:
        parts.append(_format_unit(minutes, "minute"))
    if seconds or not parts:
        parts.append(_format_unit(seconds, "second"))
    return " and ".join(parts[:2])


def _format_unit(amount: int, unit: str) -> str:
    suffix = "" if amount == 1 else "s"
    return f"{amount} {unit}{suffix}"


register_tool(
    ToolSpec(
        name="start_timer",
        description=(
            "start a timer for a specific duration; use this only when the user has given "
            "an explicit time length."
        ),
        args_schema={
            "duration_seconds": "Length of the timer in seconds.",
            "duration_minutes": "Optional length of the timer in minutes.",
            "duration_hours": "Optional length of the timer in hours.",
            "duration_text": "Optional natural duration like 30s or 2min.",
            "label": "Optional short timer label.",
        },
        handler=_start_timer,
    )
)

register_tool(
    ToolSpec(
        name="list_timers",
        description="list timers that have been created through the timer tool.",
        args_schema={},
        handler=_list_timers,
    )
)

register_tool(
    ToolSpec(
        name="cancel_timers",
        description="cancel active timers that were created through the timer tool.",
        args_schema={
            "timer_id": "Optional timer id to cancel. If omitted, cancel all active timers.",
            "label": "Optional timer label to cancel. If omitted, cancel all active timers.",
        },
        handler=_cancel_timers,
    )
)
