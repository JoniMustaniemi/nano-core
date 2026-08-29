from helpers.agent_fixtures import ShouldNotBeCalledClient, patch_agent
from sqlmodel import Session, select
from starlette.testclient import TestClient

import app.memory.db as db
from app.memory import repository
from app.memory.models import ChatMessage


def test_chat_stop_stopwatch_updates_status(api_client: TestClient, monkeypatch, tmp_path) -> None:
    client = ShouldNotBeCalledClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )
    stopwatch_one = repository.add_stopwatch("One")
    stopwatch_two = repository.add_stopwatch("Two")
    assert stopwatch_one.id is not None
    assert stopwatch_two.id is not None

    response = api_client.post(
        "/api/chat",
        json={"message": f"Stop stopwatch {stopwatch_two.id}", "mode": "agent"},
    )
    status = api_client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["content"] == ""
    assert response.json()["speak"] is False
    active_ids = [stopwatch["id"] for stopwatch in status.json()["active_stopwatches"]]
    assert active_ids == [stopwatch_one.id]


def test_chat_stop_stopwatch_is_silent_and_does_not_persist_messages(
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
    stopwatch = repository.add_stopwatch("Lap")
    assert stopwatch.id is not None

    before = _chat_message_count()
    response = api_client.post(
        "/api/chat",
        json={"message": f"Stop stopwatch {stopwatch.id}", "mode": "agent"},
    )
    after = _chat_message_count()

    assert response.status_code == 200
    assert after == before


def test_chat_stop_stopwatch_failure_reports_error_without_persisting_messages(
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
        json={"message": "Stop stopwatch 99999", "mode": "agent"},
    )
    after = _chat_message_count()

    assert response.status_code == 200
    assert "No matching active stopwatches to stop." in response.json()["content"]
    assert response.json()["speak"] is False
    assert after == before


def test_chat_stop_stopwatch_accepts_trailing_period(
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
    stopwatch_one = repository.add_stopwatch("One")
    stopwatch_two = repository.add_stopwatch("Two")
    assert stopwatch_one.id is not None
    assert stopwatch_two.id is not None

    response = api_client.post(
        "/api/chat",
        json={"message": f"Stop stopwatch {stopwatch_two.id}.", "mode": "agent"},
    )
    status = api_client.get("/api/status")

    assert response.status_code == 200
    active_ids = [stopwatch["id"] for stopwatch in status.json()["active_stopwatches"]]
    assert active_ids == [stopwatch_one.id]


def _chat_message_count() -> int:
    with Session(db.engine) as session:
        return len(list(session.exec(select(ChatMessage))))
