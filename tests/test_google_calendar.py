from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from app.integrations import google_calendar
from app.integrations.google_calendar import (
    GoogleCalendarAuthenticationError,
    GoogleCalendarNotFoundError,
    configured_calendar_ids,
    format_available_calendars,
    format_upcoming_events,
    get_event_start,
    list_upcoming_events,
    resolve_calendar_ids,
)
from app.tools import get_tool


def test_configured_calendar_ids_defaults_to_primary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        google_calendar,
        "get_settings",
        lambda: SimpleNamespace(google_calendar_ids=""),
    )

    assert configured_calendar_ids() == ["primary"]


def test_configured_calendar_ids_parses_comma_separated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        google_calendar,
        "get_settings",
        lambda: SimpleNamespace(
            google_calendar_ids=" primary , work@company.com , family@group.calendar.google.com "
        ),
    )

    assert configured_calendar_ids() == [
        "primary",
        "work@company.com",
        "family@group.calendar.google.com",
    ]


def test_resolve_calendar_ids_uses_override() -> None:
    assert resolve_calendar_ids("work@company.com") == ["work@company.com"]


def test_format_available_calendars_renders_numbered_list() -> None:
    calendars = [
        {"id": "primary", "summary": "Personal", "primary": "true"},
        {"id": "work@company.com", "summary": "Work", "primary": "false"},
    ]

    result = format_available_calendars(calendars)

    assert "Available calendars:" in result
    assert "1. Personal (primary) — id: primary" in result
    assert "2. Work — id: work@company.com" in result


def test_get_event_start_prefers_datetime() -> None:
    event = {"start": {"dateTime": "2026-08-03T14:00:00+03:00", "date": "2026-08-03"}}

    assert get_event_start(event) == "2026-08-03T14:00:00+03:00"


def test_get_event_start_falls_back_to_date() -> None:
    event = {"start": {"date": "2026-08-03"}}

    assert get_event_start(event) == "2026-08-03"


def test_format_upcoming_events_empty() -> None:
    assert format_upcoming_events([]) == "No upcoming events."


def test_format_upcoming_events_renders_lines() -> None:
    events = [
        {"summary": "Team sync", "start": {"dateTime": "2026-08-03T14:00:00+03:00"}},
        {"start": {"date": "2026-08-04"}},
    ]

    result = format_upcoming_events(events)

    assert result == "2026-08-03T14:00:00+03:00: Team sync\n2026-08-04: (Untitled event)"


def test_format_upcoming_events_adds_calendar_labels_for_multiple_calendars() -> None:
    events = [
        {
            "summary": "Team sync",
            "start": {"dateTime": "2026-08-03T14:00:00+03:00"},
            "_calendar_summary": "Work",
        },
        {
            "summary": "Dentist",
            "start": {"dateTime": "2026-08-03T15:00:00+03:00"},
            "_calendar_summary": "Personal",
        },
    ]

    result = format_upcoming_events(events)

    assert result == (
        "2026-08-03T14:00:00+03:00 [Work]: Team sync\n2026-08-03T15:00:00+03:00 [Personal]: Dentist"
    )


def test_list_upcoming_events_missing_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        google_calendar,
        "get_settings",
        lambda: SimpleNamespace(
            google_token_path=str(tmp_path / "missing-token.json"),
            google_calendar_ids="primary",
        ),
    )

    with pytest.raises(GoogleCalendarAuthenticationError, match="token.json is missing"):
        list_upcoming_events()


def test_list_upcoming_events_merges_multiple_calendars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events_resource = MagicMock()

    def list_events(**kwargs: object) -> MagicMock:
        execute = MagicMock()
        calendar_id = kwargs.get("calendarId")
        if calendar_id == "primary":
            execute.execute.return_value = {
                "items": [
                    {
                        "summary": "Morning standup",
                        "start": {"dateTime": "2026-08-03T09:00:00+03:00"},
                    },
                ],
            }
        else:
            execute.execute.return_value = {
                "items": [
                    {
                        "summary": "Late meeting",
                        "start": {"dateTime": "2026-08-03T16:00:00+03:00"},
                    },
                ],
            }
        return execute

    events_resource.list.side_effect = list_events

    service = MagicMock()
    service.calendarList.return_value.list.return_value.execute.return_value = {
        "items": [
            {"id": "primary", "summary": "Personal", "primary": True},
            {"id": "work@company.com", "summary": "Work"},
        ],
    }
    service.events.return_value = events_resource

    monkeypatch.setattr(
        google_calendar,
        "get_settings",
        lambda: SimpleNamespace(google_calendar_ids="primary,work@company.com"),
    )
    monkeypatch.setattr(google_calendar, "get_calendar_service", lambda: service)

    events = list_upcoming_events(maximum_results=5)

    assert [event["summary"] for event in events] == ["Morning standup", "Late meeting"]
    assert events[0]["_calendar_summary"] == "Personal"
    assert events[1]["_calendar_summary"] == "Work"


def test_list_upcoming_events_raises_for_unknown_calendar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = MagicMock()
    service.calendarList.return_value.list.return_value.execute.return_value = {
        "items": [{"id": "primary", "summary": "Personal", "primary": True}],
    }

    monkeypatch.setattr(google_calendar, "get_calendar_service", lambda: service)

    with pytest.raises(GoogleCalendarNotFoundError):
        list_upcoming_events(calendar_id="missing@company.com")


def test_list_upcoming_calendar_events_tool_registered() -> None:
    tool = get_tool("list_upcoming_calendar_events")

    assert tool is not None
    assert "maximum_results" in tool.args_schema
    assert "calendar_id" in tool.args_schema


def test_list_google_calendars_tool_registered() -> None:
    tool = get_tool("list_google_calendars")

    assert tool is not None
    assert tool.args_schema == {}


def test_list_upcoming_calendar_events_tool_formats_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = get_tool("list_upcoming_calendar_events")
    assert tool is not None

    monkeypatch.setattr(
        "app.tools.calendar_tools.list_upcoming_events",
        lambda maximum_results, calendar_id=None: [
            {"summary": "Standup", "start": {"dateTime": "2026-08-03T09:00:00+03:00"}},
        ],
    )

    result = tool.handler({"maximum_results": 5})

    assert result == "2026-08-03T09:00:00+03:00: Standup"


def test_list_upcoming_calendar_events_tool_handles_invalid_calendar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = get_tool("list_upcoming_calendar_events")
    assert tool is not None

    def raise_not_found(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        raise GoogleCalendarNotFoundError("missing@company.com")

    monkeypatch.setattr(
        "app.tools.calendar_tools.list_upcoming_events",
        raise_not_found,
    )
    monkeypatch.setattr(
        "app.tools.calendar_tools.list_available_calendars",
        lambda: [{"id": "primary", "summary": "Personal", "primary": "true"}],
    )

    result = tool.handler({"calendar_id": "missing@company.com"})

    assert "That calendar was not found." in result
    assert "Available calendars:" in result
    assert "id: primary" in result


def test_list_google_calendars_tool_formats_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = get_tool("list_google_calendars")
    assert tool is not None

    monkeypatch.setattr(
        "app.tools.calendar_tools.list_available_calendars",
        lambda: [{"id": "primary", "summary": "Personal", "primary": "true"}],
    )

    result = tool.handler({})

    assert "Available calendars:" in result
    assert "Personal (primary) — id: primary" in result


def test_list_upcoming_calendar_events_tool_handles_auth_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = get_tool("list_upcoming_calendar_events")
    assert tool is not None

    def raise_auth_error(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        raise GoogleCalendarAuthenticationError("token.json is missing.")

    monkeypatch.setattr(
        "app.tools.calendar_tools.list_upcoming_events",
        raise_auth_error,
    )

    result = tool.handler({})

    assert result == "token.json is missing."


def test_list_upcoming_calendar_events_tool_handles_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = get_tool("list_upcoming_calendar_events")
    assert tool is not None

    response = MagicMock(status=403)
    error = HttpError(response, b"forbidden")

    def raise_http_error(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        raise error

    monkeypatch.setattr(
        "app.tools.calendar_tools.list_upcoming_events",
        raise_http_error,
    )

    result = tool.handler({})

    assert result.startswith("Google Calendar API request failed:")
