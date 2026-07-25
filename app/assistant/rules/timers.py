from __future__ import annotations

import re
from typing import Any

from app.duration import (
    duration_seconds_from_tool_args,
    extract_duration_args,
    extract_duration_seconds,
    humanize_duration_seconds,
)

TIMER_REQUEST_TRIGGERS: tuple[str, ...] = (
    "timer",
    "countdown",
)
STOPWATCH_REQUEST_TRIGGERS: tuple[str, ...] = (
    "stopwatch",
    "stop watch",
)
TIMER_START_KEYWORDS: tuple[str, ...] = (
    "start",
    "set",
    "create",
    "begin",
    "add",
    "new",
    "make",
    "schedule",
    "launch",
    "arm",
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
TIMER_STATUS_KEYWORDS: tuple[str, ...] = (
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
STOPWATCH_STATUS_KEYWORDS: tuple[str, ...] = (
    *TIMER_STATUS_KEYWORDS,
    "what stopwatches",
    "what stopwatch",
)
_STOPWATCH_TWO_WORD_RE = re.compile(r"\bstop\s+watch(?:es)?\b", re.IGNORECASE)


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
    if not _has_timer_start_keyword(lowered):
        return False
    return extract_duration_seconds(lowered) is None


def duration_args_from_message(message: str) -> dict[str, Any] | None:
    """
    Handle duration args from message.

    Args:
        message: User message or prompt text.

    Returns:
        Dictionary containing the requested data.
    """
    return extract_duration_args(message)


def is_stopwatch_start_request(message: str) -> bool:
    """
    Return whether stopwatch start request.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    lowered = message.lower()
    if _has_timer_cancel_keyword(lowered) and not _has_stopwatch_trigger(lowered):
        return False
    return _has_stopwatch_trigger(lowered) and _has_timer_start_keyword(lowered)


def is_stopwatch_stop_request(message: str) -> bool:
    """
    Return whether stopwatch stop request.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    lowered = _normalize_stopwatch_spelling(message.lower())
    return _has_stopwatch_trigger(lowered) and _has_timer_cancel_keyword(lowered)


def is_timer_start_request(message: str) -> bool:
    """
    Return whether timer start request.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    lowered = message.lower()
    if _has_stopwatch_trigger(lowered):
        return False
    if _has_timer_cancel_keyword(lowered):
        return False
    return any(
        trigger in lowered for trigger in TIMER_REQUEST_TRIGGERS
    ) and _has_timer_start_keyword(lowered)


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
    lowered = _normalize_stopwatch_spelling(message.lower())
    if _has_timer_cancel_keyword(lowered):
        return False
    if _has_stopwatch_trigger(lowered):
        return any(keyword in lowered for keyword in STOPWATCH_STATUS_KEYWORDS)
    if not any(trigger in lowered for trigger in TIMER_REQUEST_TRIGGERS):
        return False
    return any(keyword in lowered for keyword in TIMER_STATUS_KEYWORDS)


def _normalize_stopwatch_spelling(message: str) -> str:
    return _STOPWATCH_TWO_WORD_RE.sub(
        lambda match: "stopwatches" if match.group(0).lower().endswith("es") else "stopwatch",
        message,
    )


def _has_stopwatch_trigger(lowered_message: str) -> bool:
    return any(trigger in lowered_message for trigger in STOPWATCH_REQUEST_TRIGGERS)


def _has_timer_start_keyword(lowered_message: str) -> bool:
    """
    Handle has timer start keyword.

    Args:
        lowered_message: Lowered message value.

    Returns:
        True when the condition is met; otherwise false.
    """
    return any(
        re.search(rf"\b{re.escape(keyword)}\b", lowered_message) for keyword in TIMER_START_KEYWORDS
    )


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
    seconds = duration_seconds_from_tool_args(args)
    return f"The timer is set for {humanize_duration_seconds(seconds)}."
