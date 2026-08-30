from __future__ import annotations

from datetime import UTC, datetime

from app.common.duration import humanize_duration_seconds


def format_countdown_timer(
    label: str,
    due_at: datetime | None,
    now: datetime,
) -> str:
    if due_at is None:
        return f"{label} countdown is active."
    remaining = timer_remaining_text(due_at, now)
    return f"{label} has {remaining} remaining."


def format_stopwatch(
    label: str,
    started_at: datetime,
    now: datetime,
) -> str:
    elapsed = timer_elapsed_text(started_at, now)
    return f"{label} stopwatch has been running for {elapsed}."


def timer_remaining_text(due_at: datetime, now: datetime) -> str:
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=UTC)
    remaining_seconds = max(0, int((due_at - now).total_seconds()))
    return humanize_duration_seconds(remaining_seconds)


def timer_elapsed_text(started_at: datetime, now: datetime) -> str:
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    elapsed_seconds = max(0, int((now - started_at).total_seconds()))
    return humanize_duration_seconds(elapsed_seconds)


def format_due_timer(label: str, created_at: datetime, due_at: datetime) -> tuple[str, str]:
    display_label = label.strip() or "Timer"
    duration_seconds = max(1, int((due_at - created_at).total_seconds()))
    label_suffix = "" if display_label == "Timer" else f" for {display_label}"
    return (
        "Timer complete.",
        f"Your {humanize_duration_seconds(duration_seconds)} timer{label_suffix} is complete.",
    )
