from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.integrations import google_calendar
from app.integrations.google_calendar import (
    GoogleCalendarNotFoundError,
    list_events_in_range,
)


def test_list_events_in_range_returns_normalized_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events_resource = MagicMock()
    events_resource.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "evt-1",
                "summary": "Standup",
                "start": {"dateTime": "2026-08-03T09:00:00+03:00"},
                "end": {"dateTime": "2026-08-03T09:30:00+03:00"},
                "htmlLink": "https://calendar.google.com/event/1",
            },
            {
                "id": "evt-2",
                "summary": "Holiday",
                "start": {"date": "2026-08-04"},
                "end": {"date": "2026-08-05"},
            },
        ],
    }
    service = MagicMock()
    service.events.return_value = events_resource

    monkeypatch.setattr(
        google_calendar,
        "list_available_calendars",
        lambda: [
            {
                "id": "primary",
                "summary": "Personal",
                "primary": "true",
                "background_color": "#9fc6e7",
            }
        ],
    )
    monkeypatch.setattr(google_calendar, "get_calendar_service", lambda: service)

    events = list_events_in_range(
        "primary",
        datetime(2026, 8, 1, tzinfo=UTC),
        datetime(2026, 9, 1, tzinfo=UTC),
    )

    assert events[0]["summary"] == "Standup"
    assert events[0]["all_day"] is False
    assert events[0]["html_link"] == "https://calendar.google.com/event/1"
    assert events[0]["calendar_id"] == "primary"
    assert events[0]["calendar_summary"] == "Personal"
    assert events[0]["calendar_color"] == "#9fc6e7"
    assert events[1]["all_day"] is True
    call_kwargs = events_resource.list.call_args.kwargs
    assert call_kwargs["calendarId"] == "primary"
    assert "timeMax" in call_kwargs


def test_list_events_in_range_raises_for_unknown_calendar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        google_calendar,
        "list_available_calendars",
        lambda: [{"id": "primary", "summary": "Personal", "primary": "true"}],
    )
    monkeypatch.setattr(google_calendar, "get_calendar_service", lambda: MagicMock())

    with pytest.raises(GoogleCalendarNotFoundError):
        list_events_in_range(
            "missing@company.com",
            datetime(2026, 8, 1, tzinfo=UTC),
            datetime(2026, 9, 1, tzinfo=UTC),
        )


def test_calendar_calendars_endpoint(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.calendar.list_available_calendars",
        lambda: [
            {
                "id": "primary",
                "summary": "Personal",
                "primary": "true",
                "background_color": "#9fc6e7",
            }
        ],
    )

    response = api_client.get("/api/calendar/calendars")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "primary",
            "summary": "Personal",
            "primary": True,
            "background_color": "#9fc6e7",
        },
    ]


def test_calendar_default_endpoint(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.calendar.configured_calendar_ids",
        lambda: ["primary", "work@company.com"],
    )

    response = api_client.get("/api/calendar/default")

    assert response.status_code == 200
    assert response.json() == {"calendar_id": "primary"}


def test_calendar_events_endpoint(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.calendar.list_events_in_range",
        lambda calendar_id, time_min, time_max: [
            {
                "id": "evt-1",
                "summary": "Standup",
                "start": "2026-08-03T09:00:00+03:00",
                "end": "2026-08-03T09:30:00+03:00",
                "all_day": False,
                "html_link": None,
                "calendar_id": calendar_id,
                "calendar_summary": "Personal",
                "calendar_color": "#9fc6e7",
            },
        ],
    )

    response = api_client.get(
        "/api/calendar/events",
        params={
            "calendar_id": "primary",
            "time_min": "2026-08-01T00:00:00+00:00",
            "time_max": "2026-09-01T00:00:00+00:00",
        },
    )

    assert response.status_code == 200
    assert response.json()[0]["summary"] == "Standup"
    assert response.json()[0]["calendar_summary"] == "Personal"


def test_calendar_events_endpoint_returns_404_for_missing_calendar(
    api_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_not_found(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        raise GoogleCalendarNotFoundError("missing@company.com")

    monkeypatch.setattr("app.api.calendar.list_events_in_range", raise_not_found)

    response = api_client.get(
        "/api/calendar/events",
        params={
            "calendar_id": "missing@company.com",
            "time_min": "2026-08-01T00:00:00+00:00",
            "time_max": "2026-09-01T00:00:00+00:00",
        },
    )

    assert response.status_code == 404


def test_calendar_calendars_endpoint_returns_503_when_unauthenticated(
    api_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.integrations.google_calendar import GoogleCalendarAuthenticationError

    def raise_auth_error() -> list[dict[str, str]]:
        raise GoogleCalendarAuthenticationError("token.json is missing.")

    monkeypatch.setattr("app.api.calendar.list_available_calendars", raise_auth_error)

    response = api_client.get("/api/calendar/calendars")

    assert response.status_code == 503
    assert "token.json is missing" in response.json()["detail"]
