from datetime import UTC, datetime, timedelta

from helpers.agent_fixtures import ShouldNotBeCalledClient, patch_agent
from sqlmodel import Session, select
from starlette.testclient import TestClient

import app.memory.db as db
from app.memory import repository
from app.memory.models import ChatMessage


def test_chat_rename_updates_status(api_client: TestClient, monkeypatch, tmp_path) -> None:
    client = ShouldNotBeCalledClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )
    timer = repository.add_timer("Timer", datetime.now(UTC) + timedelta(minutes=5))
    assert timer.id is not None

    response = api_client.post(
        "/api/chat",
        json={"message": f'Rename timer {timer.id} to "Pizza"', "mode": "agent"},
    )
    status = api_client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["content"] == ""
    assert response.json()["speak"] is False
    assert status.json()["active_timers"][0]["label"] == "Pizza"


def test_chat_rename_is_silent_and_does_not_persist_messages(
    api_client: TestClient,
    monkeypatch,
    tmp_path,
) -> None:
    client = ShouldNotBeCalledClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )
    timer = repository.add_timer("Timer", datetime.now(UTC) + timedelta(minutes=5))
    assert timer.id is not None

    before = _chat_message_count()
    response = api_client.post(
        "/api/chat",
        json={"message": f'Rename timer {timer.id} to "Pizza"', "mode": "agent"},
    )
    after = _chat_message_count()

    assert response.status_code == 200
    assert after == before


def test_chat_rename_failure_reports_error_without_persisting_messages(
    api_client: TestClient,
    monkeypatch,
    tmp_path,
) -> None:
    client = ShouldNotBeCalledClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )
    before = _chat_message_count()
    response = api_client.post(
        "/api/chat",
        json={"message": 'Rename timer 99999 to "Pizza"', "mode": "agent"},
    )
    after = _chat_message_count()

    assert response.status_code == 200
    assert "No matching active timer" in response.json()["content"]
    assert response.json()["speak"] is False
    assert after == before


def test_chat_rename_accepts_trailing_period(api_client: TestClient, monkeypatch, tmp_path) -> None:
    client = ShouldNotBeCalledClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )
    timer = repository.add_timer("Timer", datetime.now(UTC) + timedelta(minutes=5))
    assert timer.id is not None

    response = api_client.post(
        "/api/chat",
        json={"message": f'Rename timer {timer.id} to "Pizza".', "mode": "agent"},
    )
    status = api_client.get("/api/status")

    assert response.status_code == 200
    assert status.json()["active_timers"][0]["label"] == "Pizza"


def _chat_message_count() -> int:
    with Session(db.engine) as session:
        return len(list(session.exec(select(ChatMessage))))
