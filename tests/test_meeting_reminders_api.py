from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.meeting_reminders.service import fire_reminder
from app.memory import meeting_reminders as reminder_repo
from app.scheduler.jobs import complete_reminder


def _future_start(minutes_ahead: int = 120) -> str:
    return (datetime.now(UTC) + timedelta(minutes=minutes_ahead)).isoformat()


def _future_end(minutes_ahead: int = 180) -> str:
    return (datetime.now(UTC) + timedelta(minutes=minutes_ahead)).isoformat()


def _mock_calendar_connected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.meeting_reminders.ensure_calendar_connected",
        lambda: None,
    )


def test_put_creates_meeting_reminder(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_calendar_connected(monkeypatch)
    monkeypatch.setattr("app.meeting_reminders.service._schedule_reminder", lambda *_args: None)

    start = _future_start(120)
    end = _future_end(180)
    response = api_client.put(
        "/api/calendar/meeting-reminders",
        json={
            "calendar_id": "primary",
            "event_id": "evt-1",
            "start": start,
            "end": end,
            "summary": "Team sync",
            "all_day": False,
            "lead_minutes": 30,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["calendar_id"] == "primary"
    assert body["event_id"] == "evt-1"
    assert body["summary"] == "Team sync"
    assert body["lead_minutes"] == 30
    assert body["fired_at"] is None
    assert body["id"].startswith("rem_")

    expected_remind_at = datetime.fromisoformat(start) - timedelta(minutes=30)
    assert body["remind_at"] == expected_remind_at.isoformat()


def test_put_updates_existing_reminder_and_clears_fired_at(
    api_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_calendar_connected(monkeypatch)
    monkeypatch.setattr("app.meeting_reminders.service._schedule_reminder", lambda *_args: None)

    start = _future_start(120)
    end = _future_end(180)
    first = api_client.put(
        "/api/calendar/meeting-reminders",
        json={
            "calendar_id": "primary",
            "event_id": "evt-1",
            "start": start,
            "end": end,
            "summary": "Team sync",
            "all_day": False,
            "lead_minutes": 30,
        },
    )
    reminder_id = first.json()["id"]
    reminder_repo.mark_reminder_fired(reminder_id)

    second = api_client.put(
        "/api/calendar/meeting-reminders",
        json={
            "calendar_id": "primary",
            "event_id": "evt-1",
            "start": start,
            "end": end,
            "summary": "Team sync",
            "all_day": False,
            "lead_minutes": 60,
        },
    )

    assert second.status_code == 200
    body = second.json()
    assert body["id"] == reminder_id
    assert body["lead_minutes"] == 60
    assert body["fired_at"] is None
    expected_remind_at = datetime.fromisoformat(start) - timedelta(minutes=60)
    assert body["remind_at"] == expected_remind_at.isoformat()


def test_get_lists_active_reminders_only(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_calendar_connected(monkeypatch)
    monkeypatch.setattr("app.meeting_reminders.service._schedule_reminder", lambda *_args: None)

    active_start = _future_start(120)
    active_end = _future_end(180)
    api_client.put(
        "/api/calendar/meeting-reminders",
        json={
            "calendar_id": "primary",
            "event_id": "evt-active",
            "start": active_start,
            "end": active_end,
            "summary": "Active meeting",
            "all_day": False,
            "lead_minutes": 15,
        },
    )

    fired_start = _future_start(240)
    fired_end = _future_end(300)
    fired = api_client.put(
        "/api/calendar/meeting-reminders",
        json={
            "calendar_id": "primary",
            "event_id": "evt-fired",
            "start": fired_start,
            "end": fired_end,
            "summary": "Fired meeting",
            "all_day": False,
            "lead_minutes": 15,
        },
    )
    reminder_repo.mark_reminder_fired(fired.json()["id"])

    past_start = (datetime.now(UTC) - timedelta(minutes=30)).isoformat()
    past_end = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    reminder_repo.upsert_reminder(
        calendar_id="primary",
        event_id="evt-past",
        start=datetime.fromisoformat(past_start),
        end=datetime.fromisoformat(past_end),
        summary="Past meeting",
        all_day=False,
        lead_minutes=15,
        remind_at=datetime.fromisoformat(past_start) - timedelta(minutes=15),
    )

    response = api_client.get("/api/calendar/meeting-reminders")

    assert response.status_code == 200
    reminders = response.json()
    assert len(reminders) == 1
    assert reminders[0]["event_id"] == "evt-active"


def test_delete_meeting_reminder_returns_204(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_calendar_connected(monkeypatch)
    unscheduled: list[str] = []
    monkeypatch.setattr(
        "app.meeting_reminders.service._unschedule_reminder",
        lambda reminder_id: unscheduled.append(reminder_id),
    )
    monkeypatch.setattr("app.meeting_reminders.service._schedule_reminder", lambda *_args: None)

    start = _future_start(120)
    end = _future_end(180)
    created = api_client.put(
        "/api/calendar/meeting-reminders",
        json={
            "calendar_id": "primary",
            "event_id": "evt-delete",
            "start": start,
            "end": end,
            "summary": "Delete me",
            "all_day": False,
            "lead_minutes": 30,
        },
    )
    reminder_id = created.json()["id"]

    response = api_client.delete(
        "/api/calendar/meeting-reminders",
        params={
            "calendar_id": "primary",
            "event_id": "evt-delete",
            "start": start,
        },
    )

    assert response.status_code == 204
    assert reminder_repo.get_reminder(reminder_id) is None
    assert unscheduled == [reminder_id]

    missing = api_client.delete(
        "/api/calendar/meeting-reminders",
        params={
            "calendar_id": "primary",
            "event_id": "evt-delete",
            "start": start,
        },
    )
    assert missing.status_code == 204


def test_put_rejects_all_day_event(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_calendar_connected(monkeypatch)

    response = api_client.put(
        "/api/calendar/meeting-reminders",
        json={
            "calendar_id": "primary",
            "event_id": "evt-all-day",
            "start": _future_start(120),
            "end": _future_end(180),
            "summary": "Holiday",
            "all_day": True,
            "lead_minutes": 30,
        },
    )

    assert response.status_code == 400
    assert "All-day" in response.json()["detail"]


def test_put_rejects_invalid_lead_minutes(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_calendar_connected(monkeypatch)

    response = api_client.put(
        "/api/calendar/meeting-reminders",
        json={
            "calendar_id": "primary",
            "event_id": "evt-bad-lead",
            "start": _future_start(120),
            "end": _future_end(180),
            "summary": "Bad lead",
            "all_day": False,
            "lead_minutes": 45,
        },
    )

    assert response.status_code == 422


def test_put_rejects_past_start(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_calendar_connected(monkeypatch)

    past_start = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    past_end = (datetime.now(UTC) + timedelta(minutes=20)).isoformat()
    response = api_client.put(
        "/api/calendar/meeting-reminders",
        json={
            "calendar_id": "primary",
            "event_id": "evt-past",
            "start": past_start,
            "end": past_end,
            "summary": "Past meeting",
            "all_day": False,
            "lead_minutes": 30,
        },
    )

    assert response.status_code == 400
    assert "future" in response.json()["detail"]


def test_put_rejects_invalid_datetime(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_calendar_connected(monkeypatch)

    response = api_client.put(
        "/api/calendar/meeting-reminders",
        json={
            "calendar_id": "primary",
            "event_id": "evt-bad-date",
            "start": "not-a-date",
            "end": _future_end(180),
            "summary": "Bad date",
            "all_day": False,
            "lead_minutes": 30,
        },
    )

    assert response.status_code == 422
    assert "start" in response.json()["detail"]


def test_meeting_reminders_return_503_when_calendar_not_connected(
    api_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.integrations.google_calendar import GoogleCalendarAuthenticationError

    def raise_auth_error() -> None:
        raise GoogleCalendarAuthenticationError("token.json is missing.")

    monkeypatch.setattr(
        "app.api.meeting_reminders.ensure_calendar_connected",
        raise_auth_error,
    )

    response = api_client.get("/api/calendar/meeting-reminders")

    assert response.status_code == 503
    assert "token.json is missing" in response.json()["detail"]


def test_complete_reminder_fires_and_announces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    start = now + timedelta(minutes=10)
    remind_at = now - timedelta(minutes=1)
    reminder = reminder_repo.upsert_reminder(
        calendar_id="primary",
        event_id="evt-fire",
        start=start,
        end=start + timedelta(minutes=30),
        summary="Standup",
        all_day=False,
        lead_minutes=15,
        remind_at=remind_at,
    )

    logged: list[tuple[str, str | None]] = []
    announced: list[str] = []
    unscheduled: list[str] = []

    monkeypatch.setattr(
        "app.meeting_reminders.service.activity.log",
        lambda **kwargs: logged.append((kwargs["title"], kwargs.get("detail"))),
    )
    monkeypatch.setattr(
        "app.meeting_reminders.service.activity.announce_voice",
        lambda message: announced.append(message),
    )
    monkeypatch.setattr(
        "app.meeting_reminders.service._unschedule_reminder",
        lambda reminder_id: unscheduled.append(reminder_id),
    )

    complete_reminder(reminder.id)

    updated = reminder_repo.get_reminder(reminder.id)
    assert updated is not None
    assert updated.fired_at is not None
    assert logged == [("Meeting reminder", "Reminder: Standup starts in 15 minutes.")]
    assert announced == ["Reminder: Standup starts in 15 minutes."]
    assert unscheduled == [reminder.id]


def test_fire_reminder_reschedules_when_remind_at_is_in_future(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    start = now + timedelta(hours=2)
    remind_at = now + timedelta(minutes=30)
    reminder = reminder_repo.upsert_reminder(
        calendar_id="primary",
        event_id="evt-later",
        start=start,
        end=start + timedelta(minutes=30),
        summary="Later meeting",
        all_day=False,
        lead_minutes=30,
        remind_at=remind_at,
    )

    scheduled: list[tuple[str, datetime]] = []
    monkeypatch.setattr(
        "app.meeting_reminders.service._schedule_reminder",
        lambda reminder_id, remind_time: scheduled.append((reminder_id, remind_time)),
    )
    monkeypatch.setattr("app.meeting_reminders.service.activity.log", MagicMock())
    monkeypatch.setattr("app.meeting_reminders.service.activity.announce_voice", MagicMock())

    fire_reminder(reminder.id)

    updated = reminder_repo.get_reminder(reminder.id)
    assert updated is not None
    assert updated.fired_at is None
    assert scheduled == [(reminder.id, remind_at)]
