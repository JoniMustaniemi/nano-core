from __future__ import annotations

import re
from typing import Any

_DIGIT_DURATION_PATTERN = re.compile(
    r"\b(\d+)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours)\b"
)
_WORD_DURATION_PATTERN = re.compile(
    r"\b((?:\ban?\b|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|"
    r"fifty|sixty|seventy|eighty|ninety|hundred|and|-|\s)+)\s*"
    r"(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours)\b"
)
_UNIT_ONLY_PATTERN = re.compile(r"\b(s|m|h)\b")
_BARE_NUMBER_PATTERN = re.compile(r"^\s*(\d+)\s*$")

_UNIT_ALIASES: dict[str, str] = {
    "s": "seconds",
    "sec": "seconds",
    "secs": "seconds",
    "second": "seconds",
    "seconds": "seconds",
    "m": "minutes",
    "min": "minutes",
    "mins": "minutes",
    "minute": "minutes",
    "minutes": "minutes",
    "h": "hours",
    "hr": "hours",
    "hrs": "hours",
    "hour": "hours",
    "hours": "hours",
}

_SMALL_NUMBER_WORDS: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
_TENS_NUMBER_WORDS: dict[str, int] = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


def extract_duration_args(message: str) -> dict[str, int] | None:
    """
    Extract duration args.

    Args:
        message: User message or prompt text.

    Returns:
        Dictionary containing the requested data.
    """
    seconds = extract_duration_seconds(message)
    if seconds is None:
        return None
    return {"duration_seconds": seconds}


def extract_duration_seconds(
    message: str,
    *,
    bare_number_unit: str | None = None,
) -> int | None:
    """
    Extract a timer duration as total seconds.

    Args:
        message: User message or prompt text.
        bare_number_unit: When set to ``minutes``, accept a bare integer reply.

    Returns:
        Total seconds when a duration is present; otherwise None.
    """
    segments = _iter_duration_segments(message)
    if segments:
        return sum(_segment_to_seconds(value, unit) for value, unit, _, _ in segments)

    lowered = message.lower()
    unit_only_match = _UNIT_ONLY_PATTERN.search(lowered)
    if unit_only_match is not None:
        unit = _normalize_unit(unit_only_match.group(1))
        if unit is not None:
            return _segment_to_seconds(1, unit)

    if bare_number_unit == "minutes":
        bare_match = _BARE_NUMBER_PATTERN.match(message.strip())
        if bare_match is not None:
            return int(bare_match.group(1)) * 60

    return None


def parse_duration_phrase(message: str) -> tuple[int, str] | None:
    """
    Parse duration phrase.

    Args:
        message: User message or prompt text.

    Returns:
        Tuple containing the requested values.
    """
    segments = _iter_duration_segments(message)
    if segments:
        value, unit, _, _ = segments[0]
        return value, unit

    lowered = message.lower()
    unit_only_match = _UNIT_ONLY_PATTERN.search(lowered)
    if unit_only_match is not None:
        normalized_unit = _normalize_unit(unit_only_match.group(1))
        if normalized_unit is not None:
            return 1, normalized_unit

    return None


def parse_duration_to_seconds(raw: str) -> int:
    """
    Parse duration to seconds.

    Args:
        raw: Raw input value to parse.

    Returns:
        Computed integer value.
    """
    seconds = extract_duration_seconds(raw)
    return seconds if seconds is not None else 0


def duration_seconds_from_tool_args(args: dict[str, Any]) -> int:
    """
    Resolve timer tool args to total seconds.

    Args:
        args: Tool argument dictionary.

    Returns:
        Computed integer value.
    """
    if "duration_seconds" in args:
        return int(args.get("duration_seconds", 0))
    if "duration_minutes" in args:
        return int(args.get("duration_minutes", 0)) * 60
    if "duration_hours" in args:
        return int(args.get("duration_hours", 0)) * 3600
    if "duration_text" in args:
        return parse_duration_to_seconds(str(args.get("duration_text", "")))
    return 0


def humanize_duration_seconds(total_seconds: int) -> str:
    """
    Format a duration in seconds for user-facing copy.

    Args:
        total_seconds: Duration value in seconds.

    Returns:
        Generated or formatted string value.
    """
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


def _iter_duration_segments(message: str) -> list[tuple[int, str, int, int]]:
    lowered = message.lower()
    segments: list[tuple[int, str, int, int]] = []

    for match in _DIGIT_DURATION_PATTERN.finditer(lowered):
        unit = _normalize_unit(match.group(2))
        if unit is not None:
            segments.append((int(match.group(1)), unit, match.start(), match.end()))

    for match in _WORD_DURATION_PATTERN.finditer(lowered):
        if any(not (match.end() <= start or match.start() >= end) for _, _, start, end in segments):
            continue
        value = _words_to_number(match.group(1))
        unit = _normalize_unit(match.group(2))
        if value is not None and unit is not None:
            segments.append((value, unit, match.start(), match.end()))

    segments.sort(key=lambda item: item[2])
    return segments


def _segment_to_seconds(value: int, unit: str) -> int:
    if unit == "seconds":
        return value
    if unit == "minutes":
        return value * 60
    return value * 3600


def _format_unit(amount: int, unit: str) -> str:
    suffix = "" if amount == 1 else "s"
    return f"{amount} {unit}{suffix}"


def _normalize_unit(unit: str) -> str | None:
    """
    Normalize unit.

    Args:
        unit: Duration unit text.

    Returns:
        Generated or formatted string value.
    """
    return _UNIT_ALIASES.get(unit)


def _words_to_number(raw: str) -> int | None:
    """
    Handle words to number.

    Args:
        raw: Raw input value to parse.

    Returns:
        Parsed value when available; otherwise None.
    """
    cleaned = raw.replace("-", " ")
    tokens = [token for token in cleaned.split() if token != "and"]
    if not tokens:
        return None
    if tokens == ["a"] or tokens == ["an"]:
        return 1

    total = 0
    current = 0
    for token in tokens:
        if token in {"a", "an"}:
            current += 1
            continue
        if token in _SMALL_NUMBER_WORDS:
            current += _SMALL_NUMBER_WORDS[token]
            continue
        if token in _TENS_NUMBER_WORDS:
            current += _TENS_NUMBER_WORDS[token]
            continue
        if token == "hundred":
            if current == 0:
                current = 1
            current *= 100
            continue
        return None

    total += current
    return total
