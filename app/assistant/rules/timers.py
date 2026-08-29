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
TIMER_RENAME_KEYWORDS: tuple[str, ...] = (
    "rename",
    "change name",
    "call it",
)
TIMER_CLEAR_ALL_KEYWORDS: tuple[str, ...] = (
    "all",
    "everything",
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
_RENAME_TIMER_BY_ID_QUOTED_RE = re.compile(
    r'^rename\s+timer\s+(?P<timer_id>\d+)\s+to\s+"(?P<new_label>[^"]+)"\s*$',
    re.IGNORECASE,
)
_RENAME_TIMER_BY_ID_UNQUOTED_RE = re.compile(
    r"^rename\s+timer\s+(?P<timer_id>\d+)\s+to\s+(?P<new_label>.+?)\s*$",
    re.IGNORECASE,
)
_RENAME_TIMER_BY_LABEL_RE = re.compile(
    r'^rename\s+the\s+timer\s+"(?P<label>[^"]+)"\s+to\s+"(?P<new_label>[^"]+)"\s*$',
    re.IGNORECASE,
)
_RENAME_STOPWATCH_BY_ID_QUOTED_RE = re.compile(
    r'^rename\s+stopwatch\s+(?P<stopwatch_id>\d+)\s+to\s+"(?P<new_label>[^"]+)"\s*$',
    re.IGNORECASE,
)
_RENAME_STOPWATCH_BY_ID_UNQUOTED_RE = re.compile(
    r"^rename\s+stopwatch\s+(?P<stopwatch_id>\d+)\s+to\s+(?P<new_label>.+?)\s*$",
    re.IGNORECASE,
)
_RENAME_STOPWATCH_BY_LABEL_RE = re.compile(
    r'^rename\s+the\s+stopwatch\s+"(?P<label>[^"]+)"\s+to\s+"(?P<new_label>[^"]+)"\s*$',
    re.IGNORECASE,
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


def is_clear_all_timers_request(message: str) -> bool:
    """
    Return whether the user wants to clear every active timer and stopwatch.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    lowered = message.lower()
    if not _has_timer_cancel_keyword(lowered):
        return False
    if not any(
        re.search(rf"\b{re.escape(keyword)}\b", lowered) for keyword in TIMER_CLEAR_ALL_KEYWORDS
    ):
        return False
    return any(trigger in lowered for trigger in TIMER_REQUEST_TRIGGERS) or "timers" in lowered


def is_timer_cancel_request(message: str) -> bool:
    """
    Return whether timer cancel request.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    lowered = message.lower()
    if _has_timer_rename_keyword(lowered):
        return False
    has_timer_trigger = any(trigger in lowered for trigger in TIMER_REQUEST_TRIGGERS)
    return has_timer_trigger and _has_timer_cancel_keyword(lowered)


def normalize_rename_command_message(message: str) -> str:
    """
    Normalize a UI rename command before regex parsing.

    Args:
        message: Raw user or UI message text.

    Returns:
        Trimmed message with normalized quotes and trailing punctuation removed.
    """
    normalized = message.strip()
    normalized = normalized.replace("\u201c", '"').replace("\u201d", '"')
    normalized = normalized.replace("\u2018", "'").replace("\u2019", "'")
    while normalized and normalized[-1] in ".!":
        normalized = normalized[:-1].rstrip()
    return normalized


def parse_timer_rename_args(message: str) -> dict[str, Any] | None:
    """
    Parse rename timer arguments when the message matches a supported phrase.

    Args:
        message: User message or prompt text.

    Returns:
        Tool argument dictionary for rename_timer, or None when no phrase matches.
    """
    normalized = normalize_rename_command_message(message)
    for pattern in (
        _RENAME_TIMER_BY_ID_QUOTED_RE,
        _RENAME_TIMER_BY_ID_UNQUOTED_RE,
        _RENAME_TIMER_BY_LABEL_RE,
    ):
        match = pattern.match(normalized)
        if match is None:
            continue
        args = match.groupdict()
        if args.get("timer_id") is not None:
            return {
                "timer_id": int(args["timer_id"]),
                "new_label": args["new_label"].strip(),
            }
        return {
            "label": args["label"].strip(),
            "new_label": args["new_label"].strip(),
        }
    return None


def parse_stopwatch_rename_args(message: str) -> dict[str, Any] | None:
    """
    Parse rename stopwatch arguments when the message matches a supported phrase.

    Args:
        message: User message or prompt text.

    Returns:
        Tool argument dictionary for rename_stopwatch, or None when no phrase matches.
    """
    normalized = normalize_rename_command_message(message)
    for pattern in (
        _RENAME_STOPWATCH_BY_ID_QUOTED_RE,
        _RENAME_STOPWATCH_BY_ID_UNQUOTED_RE,
        _RENAME_STOPWATCH_BY_LABEL_RE,
    ):
        match = pattern.match(normalized)
        if match is None:
            continue
        args = match.groupdict()
        if args.get("stopwatch_id") is not None:
            return {
                "stopwatch_id": int(args["stopwatch_id"]),
                "new_label": args["new_label"].strip(),
            }
        return {
            "label": args["label"].strip(),
            "new_label": args["new_label"].strip(),
        }
    return None


def is_timer_rename_request(message: str) -> bool:
    """
    Return whether the user wants to rename a countdown timer.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    return parse_timer_rename_args(message) is not None


def is_stopwatch_rename_request(message: str) -> bool:
    """
    Return whether the user wants to rename a stopwatch.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    return parse_stopwatch_rename_args(message) is not None


def is_silent_rename_command(message: str) -> bool:
    """
    Return whether the message is a UI rename control command.

    Args:
        message: User message or prompt text.

    Returns:
        True when the message parses as a timer or stopwatch rename command.
    """
    return is_timer_rename_request(message) or is_stopwatch_rename_request(message)


def rename_timer_args_from_message(message: str) -> dict[str, Any]:
    """
    Parse rename timer arguments from a UI or voice message.

    Args:
        message: User message or prompt text.

    Returns:
        Tool argument dictionary for rename_timer.
    """
    return parse_timer_rename_args(message) or {}


def rename_stopwatch_args_from_message(message: str) -> dict[str, Any]:
    """
    Parse rename stopwatch arguments from a UI or voice message.

    Args:
        message: User message or prompt text.

    Returns:
        Tool argument dictionary for rename_stopwatch.
    """
    return parse_stopwatch_rename_args(message) or {}


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


def _has_timer_rename_keyword(lowered_message: str) -> bool:
    """
    Return whether the message contains a rename keyword.

    Args:
        lowered_message: Lowered message value.

    Returns:
        True when the condition is met; otherwise false.
    """
    return any(keyword in lowered_message for keyword in TIMER_RENAME_KEYWORDS)


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
