import pytest

from app.duration import (
    _normalize_unit,
    _words_to_number,
    extract_duration_args,
    parse_duration_phrase,
    parse_duration_to_seconds,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("zero", 0),
        ("one", 1),
        ("a", 1),
        ("an", 1),
        ("hundred", 100),
        ("one hundred", 100),
        ("five hundred", 500),
        ("twenty one", 21),
        ("twenty-one", 21),
        ("not a number", None),
        ("", None),
    ],
)
def test_words_to_number(raw: str, expected: int | None) -> None:
    assert _words_to_number(raw) == expected


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        ("s", "seconds"),
        ("sec", "seconds"),
        ("secs", "seconds"),
        ("second", "seconds"),
        ("seconds", "seconds"),
        ("m", "minutes"),
        ("min", "minutes"),
        ("mins", "minutes"),
        ("minute", "minutes"),
        ("minutes", "minutes"),
        ("h", "hours"),
        ("hr", "hours"),
        ("hrs", "hours"),
        ("hour", "hours"),
        ("hours", "hours"),
        ("month", None),
        ("unknown", None),
    ],
)
def test_normalize_unit(unit: str, expected: str | None) -> None:
    assert _normalize_unit(unit) == expected


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("30s", (30, "seconds")),
        ("2m", (2, "minutes")),
        ("0s", (0, "seconds")),
        ("five minutes", (5, "minutes")),
        ("a minute", (1, "minutes")),
        ("an hour", (1, "hours")),
        ("zero seconds", (0, "seconds")),
        ("one second", (1, "seconds")),
        ("hundred seconds", (100, "seconds")),
        ("s", (1, "seconds")),
        ("m", (1, "minutes")),
        ("h", (1, "hours")),
        ("soon", None),
        ("", None),
    ],
)
def test_parse_duration_phrase(message: str, expected: tuple[int, str] | None) -> None:
    assert parse_duration_phrase(message) == expected


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("30 seconds", {"duration_seconds": 30}),
        ("zero seconds", {"duration_seconds": 0}),
        ("one minute", {"duration_minutes": 1}),
        ("an hour", {"duration_hours": 1}),
        ("2 hours", {"duration_hours": 2}),
        ("soon", None),
    ],
)
def test_extract_duration_args(message: str, expected: dict[str, int] | None) -> None:
    assert extract_duration_args(message) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("30s", 30),
        ("5 minutes", 300),
        ("1 hour", 3600),
        ("s", 1),
        ("m", 60),
        ("h", 3600),
        ("zero seconds", 0),
        ("soon", 0),
    ],
)
def test_parse_duration_to_seconds(raw: str, expected: int) -> None:
    assert parse_duration_to_seconds(raw) == expected
