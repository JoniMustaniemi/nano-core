from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from app.memory import repository
from app.tools.base import ToolSpec
from app.tools.registry import register_tool


def _start_timer(args: dict[str, Any]) -> str:
    duration_seconds = _resolve_duration_seconds(args)
    if duration_seconds <= 0:
        return "Timer duration must be greater than 0."

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
    if "duration_text" in args:
        return _parse_duration_text(str(args.get("duration_text", "")))
    return 0


def _parse_duration_text(raw: str) -> int:
    text = raw.strip().lower()
    if not text:
        return 0

    match = re.fullmatch(r"(\d+)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes)", text)
    if match is None:
        return 0

    value = int(match.group(1))
    unit = match.group(2)
    if unit.startswith("s"):
        return value
    return value * 60


def _list_timers(args: dict[str, Any]) -> str:
    del args
    reminders = repository.list_reminders()
    timers = [reminder for reminder in reminders if reminder.content.startswith("[timer] ")]
    if not timers:
        return "No timers."
    return "\n".join(
        f"{timer.id}: {timer.content.removeprefix('[timer] ')} @ {timer.due_at.isoformat()}"
        for timer in timers
    )


register_tool(
    ToolSpec(
        name="start_timer",
        description=(
            "start a timer; use this when the user asks you to set a timer or remind them "
            "after a short delay."
        ),
        args_schema={
            "duration_seconds": "Length of the timer in seconds.",
            "duration_minutes": "Optional length of the timer in minutes.",
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
