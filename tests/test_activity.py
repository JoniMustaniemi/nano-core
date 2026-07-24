from fastapi.testclient import TestClient
from helpers.agent_fixtures import wrap_with_alignment_intercept

from app.assistant.pending import pending_interactions
from app.config import get_settings
from app.main import app
from app.runtime.status_copy import RECEIVED_TITLE, STANDBY_GREETINGS, route_acknowledgment


class _FakeClient:
    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        assert messages
        assert messages[-1]["content"] == "Hello"
        return "Hi there!"


class _HealthClient:
    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        assert messages
        return "My health checks are complete."


def test_chat_updates_activity(monkeypatch) -> None:
    """
    Verify that chat updates activity.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.
    """
    monkeypatch.setattr(
        "app.assistant.service.get_llm_client",
        lambda: wrap_with_alignment_intercept(_FakeClient()),
    )

    with TestClient(app) as client:
        response = client.post("/chat", json={"message": "Hello", "mode": "chat"})
        status = client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["content"] == "Hi there!"

    payload = status.json()
    assert payload["state"] == "standby"
    assert payload["headline"] in set(STANDBY_GREETINGS) | {"I'm in standby."}
    assert any(event["source"] == "assistant.chat" for event in payload["events"])


def test_health_check_sets_working_activity(monkeypatch) -> None:
    """
    Verify that health diagnostics report working activity.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.
    """
    monkeypatch.setattr(
        "app.assistant.orchestrator.get_llm_client",
        lambda: wrap_with_alignment_intercept(_HealthClient()),
    )
    monkeypatch.setattr(
        "app.assistant.tool_runner.GladosVoiceService.announce",
        lambda self, text: None,
    )

    with TestClient(app) as client:
        response = client.post("/chat", json={"message": "Check your health.", "mode": "agent"})
        status = client.get("/api/status")

    assert response.status_code == 200
    payload = status.json()
    assert payload["state"] == "standby"
    assert any(
        event["state"] == "working" and event["title"] == "I'm running a health check."
        for event in payload["events"]
    )


def test_route_acknowledgment_uses_personality_copy() -> None:
    title, detail = route_acknowledgment(mode="tool", tool_name="check_health")
    assert title == "I'm running a health check."
    assert detail

    identity_title, identity_detail = route_acknowledgment(mode="identity")
    assert identity_title == "I'm introducing myself."
    assert identity_detail


def test_agent_request_acknowledges_before_processing(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.assistant.service.get_llm_client",
        lambda: wrap_with_alignment_intercept(_FakeClient()),
    )

    with TestClient(app) as client:
        response = client.post("/chat", json={"message": "Hello", "mode": "chat"})
        status = client.get("/api/status")

    assert response.status_code == 200
    payload = status.json()
    assert any(
        event["state"] == "working" and event["title"] == RECEIVED_TITLE
        for event in payload["events"]
    )


def test_status_snapshot_exposes_pending_kind() -> None:
    settings = get_settings()
    pending_interactions.set(
        conversation_id=settings.proactive_conversation_id,
        kind="timer_duration",
        payload={},
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/status")
        assert response.status_code == 200
        assert response.json()["pending"] == {"kind": "timer_duration"}
    finally:
        pending_interactions.clear(settings.proactive_conversation_id)


def test_greeting_api_returns_standby_greeting() -> None:
    from app.runtime.status_copy import STANDBY_GREETINGS, choose_standby_greeting

    assert len(STANDBY_GREETINGS) >= 10
    assert choose_standby_greeting() in STANDBY_GREETINGS

    with TestClient(app) as client:
        response = client.get("/api/greeting")
    assert response.status_code == 200
    assert response.json()["greeting"] in STANDBY_GREETINGS
