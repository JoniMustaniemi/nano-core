from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.main import app
from app.memory import repository
from app.memory.internal_note_service import InternalNoteService
from app.proactive.types import ProactiveOffer


def test_storage_snapshot_exposes_saved_records() -> None:
    """
    Verify that storage snapshot exposes saved records.

    Returns:
        None.
    """
    repository.add_chat_message(conversation_id="default", role="user", content="hello")
    offer = ProactiveOffer(
        kind="self_improvement_suggestion",
        title="Improve timers",
        summary="Make timer errors clearer.",
        payload={"goal": "clearer timer errors"},
        created_at=datetime.now(UTC),
    )
    InternalNoteService().record_from_offer(offer, next_attempt_at=datetime.now(UTC))

    with TestClient(app) as client:
        storage = client.get("/api/storage")

    assert storage.status_code == 200
    payload = storage.json()
    assert payload["chat_messages"][0]["content"] == "hello"
    assert payload["internal_notes"][0]["title"] == "Improve timers"
    assert "notes" not in payload
    assert "reminders" not in payload
