from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.main import app


def test_notes_and_reminders_round_trip() -> None:
    due_at = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()

    with TestClient(app) as client:
        note_response = client.post("/api/notes", json={"content": "buy milk"})
        reminder_response = client.post(
            "/api/reminders",
            json={"content": "stretch", "due_at": due_at},
        )
        notes = client.get("/api/notes")
        reminders = client.get("/api/reminders")

    assert note_response.status_code == 200
    assert reminder_response.status_code == 200
    assert notes.json()[0]["content"] == "buy milk"
    assert reminders.json()[0]["content"] == "stretch"
