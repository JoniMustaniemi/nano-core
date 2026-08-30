from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.common.duration import duration_seconds_from_tool_args
from app.memory import repository
from app.memory.models import Timer
from app.memory.repository import COUNTDOWN_KIND, STOPWATCH_KIND
from app.runtime.activity import activity
from app.runtime.status_copy import STOPWATCH_STARTED_MESSAGE
from app.scheduler.jobs import schedule_timer, unschedule_timer
from app.timers.formatting import format_countdown_timer, format_stopwatch
from app.timers.labels import (
    normalize_label,
    resolve_rename_target,
    timer_matches_cancel_request,
)
from app.tools.errors import ToolError


def remove_countdown_timer(timer_id: int) -> bool:
    timer = repository.get_timer(timer_id)
    if timer is None or timer.kind != COUNTDOWN_KIND:
        return False
    unschedule_timer(timer_id)
    return repository.delete_timer(timer_id)


def remove_stopwatch(stopwatch_id: int) -> bool:
    stopwatch = repository.get_timer(stopwatch_id)
    if stopwatch is None or stopwatch.kind != STOPWATCH_KIND:
        return False
    return repository.delete_timer(stopwatch_id)


def start_timer(args: dict[str, Any]) -> str:
    duration_seconds = duration_seconds_from_tool_args(args)
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


def start_stopwatch(args: dict[str, Any]) -> str:
    label = str(args.get("label", "")).strip() or "Stopwatch"
    repository.add_stopwatch(label)
    activity.log(
        title=STOPWATCH_STARTED_MESSAGE,
        detail=label,
        source="assistant.flows.timer",
    )
    return STOPWATCH_STARTED_MESSAGE


def list_timers(args: dict[str, Any]) -> str:
    del args
    countdown_timers = _active_countdown_timers()
    stopwatches = _active_stopwatches()
    if not countdown_timers and not stopwatches:
        return "No active timers."

    now = datetime.now(UTC)
    lines: list[str] = []
    for timer in countdown_timers:
        lines.append(format_countdown_timer(timer.label, timer.due_at, now))
    for stopwatch in stopwatches:
        lines.append(format_stopwatch(stopwatch.label, stopwatch.created_at, now))

    total = len(lines)
    if total == 1:
        return f"You have one timer active. {lines[0]}"
    return f"You have {total} timers active:\n" + "\n".join(lines)


def cancel_timers(args: dict[str, Any]) -> str:
    timer_id = args.get("timer_id")
    label = str(args.get("label", "")).strip().lower()
    timers = _active_countdown_timers()
    selected = [
        timer
        for timer in timers
        if timer_matches_cancel_request(timer.id, timer.label, timer_id, label)
    ]

    if not selected:
        if timer_id not in (None, "") or label:
            raise ToolError("No matching active timers to cancel.")
        return "No active timers to cancel."

    labels: list[str] = []
    for timer in selected:
        if timer.id is not None:
            remove_countdown_timer(timer.id)
        labels.append(timer.label)

    count = len(selected)
    noun = "timer" if count == 1 else "timers"
    if count == 1:
        return f"Cancelled 1 {noun}."
    return f"Cancelled {count} {noun}: {', '.join(labels)}."


def clear_all_timers(args: dict[str, Any]) -> str:
    del args
    countdown_timers = _active_countdown_timers()
    stopwatches = _active_stopwatches()
    if not countdown_timers and not stopwatches:
        return "No active timers."

    for timer in countdown_timers:
        if timer.id is not None:
            remove_countdown_timer(timer.id)

    for stopwatch in stopwatches:
        if stopwatch.id is not None:
            remove_stopwatch(stopwatch.id)

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


def stop_stopwatches(args: dict[str, Any]) -> str:
    stopwatch_id = args.get("stopwatch_id")
    label = str(args.get("label", "")).strip().lower()
    stopwatches = _active_stopwatches()
    selected = [
        stopwatch
        for stopwatch in stopwatches
        if timer_matches_cancel_request(stopwatch.id, stopwatch.label, stopwatch_id, label)
    ]

    if not selected:
        if stopwatch_id not in (None, "") or label:
            raise ToolError("No matching active stopwatches to stop.")
        return "No active stopwatches."

    for stopwatch in selected:
        if stopwatch.id is not None:
            remove_stopwatch(stopwatch.id)

    activity.log(
        title="Stopwatch stopped.",
        detail="",
        source="assistant.flows.timer",
    )

    count = len(selected)
    if count == 1:
        return "Stopped 1 stopwatch."
    return f"Stopped {count} stopwatches."


def rename_timer(args: dict[str, Any]) -> str:
    new_label_raw = args.get("new_label")
    if new_label_raw in (None, ""):
        raise ToolError("A new label is required to rename a timer.")

    timer_id = args.get("timer_id")
    old_label = str(args.get("label", "")).strip()
    timers = _active_countdown_timers()
    target = resolve_rename_target(
        timers,
        item_id=timer_id,
        old_label=old_label,
        item_noun="timer",
    )
    new_label = normalize_label(str(new_label_raw), "Timer")
    if target.id is None:
        raise ToolError("Timer id is missing.")
    updated = repository.update_timer_label(target.id, new_label)
    if updated is None:
        raise ToolError("No matching active timer to rename.")
    return f'Renamed timer to "{new_label}".'


def rename_stopwatch(args: dict[str, Any]) -> str:
    new_label_raw = args.get("new_label")
    if new_label_raw in (None, ""):
        raise ToolError("A new label is required to rename a stopwatch.")

    stopwatch_id = args.get("stopwatch_id")
    old_label = str(args.get("label", "")).strip()
    stopwatches = _active_stopwatches()
    target = resolve_rename_target(
        stopwatches,
        item_id=stopwatch_id,
        old_label=old_label,
        item_noun="stopwatch",
    )
    new_label = normalize_label(str(new_label_raw), "Stopwatch")
    if target.id is None:
        raise ToolError("Stopwatch id is missing.")
    updated = repository.update_timer_label(target.id, new_label)
    if updated is None:
        raise ToolError("No matching active stopwatch to rename.")
    return f'Renamed stopwatch to "{new_label}".'


def _active_countdown_timers() -> list[Timer]:
    return sorted(
        repository.list_countdown_timers(), key=lambda timer: timer.due_at or datetime.min
    )


def _active_stopwatches() -> list[Timer]:
    return repository.list_stopwatches()
