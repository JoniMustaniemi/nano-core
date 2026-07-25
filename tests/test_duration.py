from app.duration import (
    _normalize_unit,
    _words_to_number,
    extract_duration_args,
    parse_duration_phrase,
    parse_duration_to_seconds,
)


def test_words_to_number() -> None:
    cases = [
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
    ]
    for raw, expected in cases:
        assert _words_to_number(raw) == expected


def test_normalize_unit() -> None:
    cases = [
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
    ]
    for unit, expected in cases:
        assert _normalize_unit(unit) == expected


def test_parse_duration_phrase() -> None:
    cases = [
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
    ]
    for message, expected in cases:
        assert parse_duration_phrase(message) == expected


def test_extract_duration_args() -> None:
    cases = [
        ("30 seconds", {"duration_seconds": 30}),
        ("zero seconds", {"duration_seconds": 0}),
        ("one minute", {"duration_minutes": 1}),
        ("an hour", {"duration_hours": 1}),
        ("2 hours", {"duration_hours": 2}),
        ("soon", None),
    ]
    for message, expected in cases:
        assert extract_duration_args(message) == expected


def test_parse_duration_to_seconds() -> None:
    cases = [
        ("30s", 30),
        ("5 minutes", 300),
        ("1 hour", 3600),
        ("s", 1),
        ("m", 60),
        ("h", 3600),
        ("zero seconds", 0),
        ("soon", 0),
    ]
    for raw, expected in cases:
        assert parse_duration_to_seconds(raw) == expected
