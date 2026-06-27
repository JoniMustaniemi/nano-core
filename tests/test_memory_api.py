from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.main import app


def test_notes_and_reminders_round_trip() -> None:
    """
    Verify that notes and reminders round trip.

    Returns:
        None.
    """
    due_at = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()

    with TestClient(app) as client:
        note_response = client.post(
            "/api/notes",
            json={"name": "Shopping", "content": "buy milk"},
        )
        reminder_response = client.post(
            "/api/reminders",
            json={"content": "stretch", "due_at": due_at},
        )
        notes = client.get("/api/notes")
        reminders = client.get("/api/reminders")

    assert note_response.status_code == 200
    assert reminder_response.status_code == 200
    assert notes.json()[0]["name"] == "Shopping"
    assert notes.json()[0]["content"] == "buy milk"
    assert reminders.json()[0]["content"] == "stretch"


def test_storage_snapshot_exposes_saved_records() -> None:
    """
    Verify that storage snapshot exposes saved records.

    Returns:
        None.
    """
    due_at = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()

    with TestClient(app) as client:
        client.post("/api/notes", json={"content": "buy milk"})
        client.post(
            "/api/reminders",
            json={"content": "stretch", "due_at": due_at},
        )
        storage = client.get("/api/storage")

    assert storage.status_code == 200
    payload = storage.json()
    assert payload["notes"][0]["name"] == "Untitled note"
    assert payload["notes"][0]["content"] == "buy milk"
    assert payload["reminders"][0]["content"] == "stretch"
    assert payload["chat_messages"] == []
