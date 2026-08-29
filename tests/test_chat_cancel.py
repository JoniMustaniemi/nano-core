from datetime import UTC, datetime, timedelta

from helpers.agent_fixtures import ShouldNotBeCalledClient, patch_agent
from sqlmodel import Session, select
from starlette.testclient import TestClient

import app.memory.db as db
from app.memory import repository
from app.memory.models import ChatMessage


def test_chat_cancel_updates_status(api_client: TestClient, monkeypatch, tmp_path) -> None:
    client = ShouldNotBeCalledClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )
    due_at = datetime.now(UTC) + timedelta(minutes=5)
    timer_one = repository.add_timer("One", due_at)
    timer_two = repository.add_timer("Two", due_at + timedelta(minutes=1))
    assert timer_one.id is not None
    assert timer_two.id is not None

    response = api_client.post(
        "/api/chat",
        json={"message": f"Cancel timer {timer_two.id}", "mode": "agent"},
    )
    status = api_client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["content"] == ""
    assert response.json()["speak"] is False
    active_ids = [timer["id"] for timer in status.json()["active_timers"]]
    assert active_ids == [timer_one.id]


def test_chat_cancel_is_silent_and_does_not_persist_messages(
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
        json={"message": f"Cancel timer {timer.id}", "mode": "agent"},
    )
    after = _chat_message_count()

    assert response.status_code == 200
    assert after == before


def test_chat_cancel_failure_reports_error_without_persisting_messages(
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
        json={"message": "Cancel timer 99999", "mode": "agent"},
    )
    after = _chat_message_count()

    assert response.status_code == 200
    assert "No matching active timers to cancel." in response.json()["content"]
    assert response.json()["speak"] is False
    assert after == before


def test_chat_cancel_accepts_trailing_period(api_client: TestClient, monkeypatch, tmp_path) -> None:
    client = ShouldNotBeCalledClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )
    due_at = datetime.now(UTC) + timedelta(minutes=5)
    timer_one = repository.add_timer("One", due_at)
    timer_two = repository.add_timer("Two", due_at + timedelta(minutes=1))
    assert timer_one.id is not None
    assert timer_two.id is not None

    response = api_client.post(
        "/api/chat",
        json={"message": f"Cancel timer {timer_two.id}.", "mode": "agent"},
    )
    status = api_client.get("/api/status")

    assert response.status_code == 200
    active_ids = [timer["id"] for timer in status.json()["active_timers"]]
    assert active_ids == [timer_one.id]


def _chat_message_count() -> int:
    with Session(db.engine) as session:
        return len(list(session.exec(select(ChatMessage))))
