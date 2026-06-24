from __future__ import annotations

import re

_DIGIT_DURATION_PATTERN = re.compile(
    r"\b(\d+)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours)\b"
)
_WORD_DURATION_PATTERN = re.compile(
    r"\b((?:an?|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|"
    r"fifty|sixty|seventy|eighty|ninety|hundred|and|-|\s)+)\s*"
    r"(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours)\b"
)

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
    parsed = parse_duration_phrase(message)
    if parsed is None:
        return None

    value, unit = parsed
    if unit == "seconds":
        return {"duration_seconds": value}
    if unit == "minutes":
        return {"duration_minutes": value}
    return {"duration_hours": value}


def parse_duration_phrase(message: str) -> tuple[int, str] | None:
    """
    Parse duration phrase.

    Args:
        message: User message or prompt text.

    Returns:
        Tuple containing the requested values.
    """
    lowered = message.lower()

    digit_match = _DIGIT_DURATION_PATTERN.search(lowered)
    if digit_match is not None:
        return int(digit_match.group(1)), _normalize_unit(digit_match.group(2))

    word_match = _WORD_DURATION_PATTERN.search(lowered)
    if word_match is None:
        return None

    value = _words_to_number(word_match.group(1))
    if value is None:
        return None
    return value, _normalize_unit(word_match.group(2))


def parse_duration_to_seconds(raw: str) -> int:
    """
    Parse duration to seconds.

    Args:
        raw: Raw input value to parse.

    Returns:
        Computed integer value.
    """
    parsed = parse_duration_phrase(raw)
    if parsed is None:
        return 0

    value, unit = parsed
    if unit == "seconds":
        return value
    if unit == "minutes":
        return value * 60
    return value * 3600


def _normalize_unit(unit: str) -> str:
    """
    Normalize unit.

    Args:
        unit: Duration unit text.

    Returns:
        Generated or formatted string value.
    """
    if unit.startswith("s"):
        return "seconds"
    if unit.startswith("m"):
        return "minutes"
    return "hours"


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
    return total if total > 0 else None
