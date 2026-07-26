from helpers.agent_fixtures import wrap_with_alignment_intercept
from helpers.voice_announce import silence_announce_voice

from app.assistant.pending import pending_interactions
from app.config import get_settings
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


def test_chat_updates_activity(api_client, monkeypatch) -> None:
    """
    Verify that chat updates activity.

    Args:
        api_client: Shared FastAPI test client.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.
    """
    monkeypatch.setattr(
        "app.assistant.orchestrator.get_llm_client",
        lambda: wrap_with_alignment_intercept(_FakeClient()),
    )

    response = api_client.post("/api/chat", json={"message": "Hello", "mode": "chat"})
    status = api_client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["content"] == "Hi there!"

    payload = status.json()
    assert payload["state"] == "standby"
    assert payload["headline"] in set(STANDBY_GREETINGS) | {"I'm in standby."}
    assert any(event["source"] == "assistant.chat" for event in payload["events"])


def test_health_check_sets_working_activity(api_client, monkeypatch) -> None:
    """
    Verify that health diagnostics report working activity.

    Args:
        api_client: Shared FastAPI test client.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.
    """
    monkeypatch.setattr(
        "app.assistant.orchestrator.get_llm_client",
        lambda: wrap_with_alignment_intercept(_HealthClient()),
    )
    silence_announce_voice(monkeypatch)

    response = api_client.post("/api/chat", json={"message": "Check your health.", "mode": "agent"})
    status = api_client.get("/api/status")

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


def test_agent_request_acknowledges_before_processing(api_client, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.assistant.orchestrator.get_llm_client",
        lambda: wrap_with_alignment_intercept(_FakeClient()),
    )

    response = api_client.post("/api/chat", json={"message": "Hello", "mode": "chat"})
    status = api_client.get("/api/status")

    assert response.status_code == 200
    payload = status.json()
    assert any(
        event["state"] == "working" and event["title"] == RECEIVED_TITLE
        for event in payload["events"]
    )


def test_status_snapshot_exposes_pending_kind(api_client) -> None:
    settings = get_settings()
    pending_interactions.set(
        conversation_id=settings.proactive_conversation_id,
        kind="timer_duration",
        payload={},
    )
    try:
        response = api_client.get("/api/status")
        assert response.status_code == 200
        assert response.json()["pending"] == {"kind": "timer_duration"}
    finally:
        pending_interactions.clear(settings.proactive_conversation_id)


def test_greeting_api_returns_standby_greeting(api_client) -> None:
    from app.runtime.status_copy import STANDBY_GREETINGS, choose_standby_greeting

    assert len(STANDBY_GREETINGS) >= 10
    assert choose_standby_greeting() in STANDBY_GREETINGS

    response = api_client.get("/api/greeting")
    assert response.status_code == 200
    assert response.json()["greeting"] in STANDBY_GREETINGS


def test_task_timer_appears_in_snapshot() -> None:
    from app.runtime.activity import activity

    activity.start_task_timer("Running tests", 300)
    try:
        snapshot = activity.snapshot()
        assert snapshot["task_timer"] == {
            "label": "Running tests",
            "started_at": snapshot["task_timer"]["started_at"],
            "expected_seconds": 300,
        }
        assert isinstance(snapshot["task_timer"]["started_at"], str)
    finally:
        activity.clear_task_timer()


def test_task_timer_cleared_on_standby() -> None:
    from app.runtime.activity import activity

    activity.start_task_timer("Lint checks", 60)
    activity.standby()
    snapshot = activity.snapshot()
    assert snapshot["task_timer"] is None


def test_task_timer_cleared_on_error() -> None:
    from app.runtime.activity import activity

    activity.start_task_timer("Running tests", 300)
    activity.error(title="Verification failed.", detail="Tests failed.")
    snapshot = activity.snapshot()
    assert snapshot["task_timer"] is None
    activity.standby()


def test_release_to_idle_returns_standby() -> None:
    from app.runtime.activity import activity
    from app.runtime.status_copy import STANDBY_GREETINGS

    activity.working(title="Opening pull request", detail="Running checks.")
    activity.release_to_idle(source="test.activity")
    snapshot = activity.snapshot()

    assert snapshot["state"] == "standby"
    assert snapshot["headline"] in set(STANDBY_GREETINGS)
    assert snapshot["task_timer"] is None


def test_chat_exception_releases_activity_to_idle(api_client, monkeypatch) -> None:
    from app.runtime.activity import activity

    activity.working(title="Opening pull request", detail="Running checks.")

    def _boom(self, message: str, mode: str = "agent"):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.assistant.service.AssistantService.respond", _boom)

    response = api_client.post(
        "/api/chat", json={"message": "Open a pull request.", "mode": "agent"}
    )
    status = api_client.get("/api/status")

    assert response.status_code == 200
    assert "went wrong" in response.json()["content"].lower()
    assert status.json()["state"] == "standby"


def test_active_timers_appear_in_snapshot() -> None:
    from datetime import UTC, datetime, timedelta

    from app.memory import repository
    from app.runtime.snapshot import build_runtime_snapshot

    due_at = datetime.now(UTC) + timedelta(minutes=5)
    timer = repository.add_timer("Tea", due_at)
    snapshot = build_runtime_snapshot()

    assert len(snapshot["active_timers"]) == 1
    entry = snapshot["active_timers"][0]
    assert entry["id"] == timer.id
    assert entry["kind"] == "countdown"
    assert entry["label"] == "Tea"
    assert entry["due_at"] == due_at.isoformat()
    assert 290 <= entry["remaining_seconds"] <= 300


def test_active_timers_empty_when_none() -> None:
    from app.runtime.snapshot import build_runtime_snapshot

    assert build_runtime_snapshot()["active_timers"] == []


def test_active_stopwatches_appear_in_snapshot() -> None:
    from datetime import UTC, datetime, timedelta

    from app.memory import repository
    from app.runtime.snapshot import build_runtime_snapshot

    started_at = datetime.now(UTC) - timedelta(seconds=42)
    stopwatch = repository.add_stopwatch("Lap", started_at=started_at)
    snapshot = build_runtime_snapshot()

    assert len(snapshot["active_timers"]) == 1
    entry = snapshot["active_timers"][0]
    assert entry["id"] == stopwatch.id
    assert entry["kind"] == "stopwatch"
    assert entry["label"] == "Lap"
    assert entry["started_at"] == started_at.isoformat()
    assert 40 <= entry["elapsed_seconds"] <= 45


def test_announce_voice_uses_single_runtime_source() -> None:
    from app.runtime.activity import VOICE_ANNOUNCE_SOURCE, activity

    activity.reset()
    event = activity.announce_voice("I'm opening a pull request.")

    assert event is not None
    assert event.source == VOICE_ANNOUNCE_SOURCE
    assert event.title == "I'm opening a pull request"
    assert event.detail == "I'm opening a pull request"


def test_announce_voice_ignores_duplicate_messages() -> None:
    from app.runtime.activity import activity

    activity.reset()
    first = activity.announce_voice("I'm opening a pull request.")
    second = activity.announce_voice("I'm opening the pull request.")

    assert first is not None
    assert second is None
