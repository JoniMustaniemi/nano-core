from fastapi.testclient import TestClient

from app.main import app


class _FakeClient:
    def complete(self, messages) -> str:
        assert messages
        assert messages[-1]["content"] == "Hello"
        return "Hi there!"


def test_chat_updates_activity(monkeypatch) -> None:
    monkeypatch.setattr("app.assistant.service.get_llm_client", lambda: _FakeClient())

    with TestClient(app) as client:
        response = client.post("/chat", json={"message": "Hello", "mode": "chat"})
        status = client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["content"] == "Hi there!"

    payload = status.json()
    assert payload["state"] == "standby"
    assert payload["headline"] == "Nano is back in standby."
    assert any(event["source"] == "assistant.chat" for event in payload["events"])
