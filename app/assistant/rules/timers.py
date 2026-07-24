from __future__ import annotations

import re
from typing import Any

from app.duration import extract_duration_args

TIMER_REQUEST_TRIGGERS: tuple[str, ...] = (
    "timer",
    "countdown",
)
TIMER_START_KEYWORDS: tuple[str, ...] = (
    "start",
    "set",
    "create",
    "begin",
)
TIMER_CANCEL_KEYWORDS: tuple[str, ...] = (
    "cancel",
    "stop",
    "delete",
    "remove",
    "clear",
    "end",
    "kill",
)


def needs_timer_duration(message: str) -> bool:
    """
    Return whether timer duration.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    lowered = message.lower()
    if _has_timer_cancel_keyword(lowered):
        return False
    if not any(trigger in lowered for trigger in TIMER_REQUEST_TRIGGERS):
        return False
    if not any(keyword in lowered for keyword in TIMER_START_KEYWORDS):
        return False
    return extract_duration_args(lowered) is None


def duration_args_from_message(message: str) -> dict[str, Any] | None:
    """
    Handle duration args from message.

    Args:
        message: User message or prompt text.

    Returns:
        Dictionary containing the requested data.
    """
    return extract_duration_args(message)


def is_timer_start_request(message: str) -> bool:
    """
    Return whether timer start request.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    lowered = message.lower()
    if _has_timer_cancel_keyword(lowered):
        return False
    return any(trigger in lowered for trigger in TIMER_REQUEST_TRIGGERS) and any(
        keyword in lowered for keyword in TIMER_START_KEYWORDS
    )


def is_timer_cancel_request(message: str) -> bool:
    """
    Return whether timer cancel request.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    lowered = message.lower()
    has_timer_trigger = any(trigger in lowered for trigger in TIMER_REQUEST_TRIGGERS)
    return has_timer_trigger and _has_timer_cancel_keyword(lowered)


def is_timer_status_request(message: str) -> bool:
    """
    Return whether timer status request.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    lowered = message.lower()
    if _has_timer_cancel_keyword(lowered):
        return False
    if not any(trigger in lowered for trigger in TIMER_REQUEST_TRIGGERS):
        return False
    status_keywords = (
        "active",
        "running",
        "left",
        "remaining",
        "status",
        "list",
        "check",
        "how long",
        "what timers",
    )
    return any(keyword in lowered for keyword in status_keywords)


def _has_timer_cancel_keyword(lowered_message: str) -> bool:
    """
    Handle has timer cancel keyword.

    Args:
        lowered_message: Lowered message value.

    Returns:
        True when the condition is met; otherwise false.
    """
    return any(
        re.search(rf"\b{re.escape(keyword)}\b", lowered_message)
        for keyword in TIMER_CANCEL_KEYWORDS
    )


def timer_confirmation(args: dict[str, Any]) -> str:
    """
    Build timer text for confirmation.

    Args:
        args: Tool argument dictionary.

    Returns:
        Generated or formatted string value.
    """
    if "duration_hours" in args:
        amount = int(args["duration_hours"])
        unit = "hour" if amount == 1 else "hours"
        return f"The timer is set for {amount} {unit}."

    if "duration_seconds" in args:
        amount = int(args["duration_seconds"])
        unit = "second" if amount == 1 else "seconds"
        return f"The timer is set for {amount} {unit}."

    amount = int(args["duration_minutes"])
    unit = "minute" if amount == 1 else "minutes"
    return f"The timer is set for {amount} {unit}."
