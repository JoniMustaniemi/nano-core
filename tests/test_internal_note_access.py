from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.assistant.agent_router import AgentRouter
from app.assistant.rules.intents import is_internal_note_list_request
from app.main import app
from app.memory.db import create_db_and_tables
from app.memory.internal_note_service import InternalNoteService
from app.proactive.types import ProactiveOffer
from app.tools import get_tool


def test_list_internal_notes_tool_formats_saved_notes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'internal.sqlite3'}")
    create_db_and_tables()

    offer = ProactiveOffer(
        kind="self_improvement_suggestion",
        title="Improve timers",
        summary="Make timer errors clearer.",
        payload={"goal": "clearer timer errors"},
        created_at=datetime.now(UTC),
    )
    InternalNoteService().record_from_offer(offer, next_attempt_at=datetime.now(UTC))

    tool = get_tool("list_internal_notes")
    assert tool is not None
    result = tool.handler({})

    assert "Improve timers" in result
    assert "Make timer errors clearer." in result
    assert "[pending]" in result


def test_storage_snapshot_includes_internal_notes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'storage.sqlite3'}")
    create_db_and_tables()

    offer = ProactiveOffer(
        kind="self_improvement_suggestion",
        title="Improve timers",
        summary="Make timer errors clearer.",
        payload={"goal": "clearer timer errors"},
        created_at=datetime.now(UTC),
    )
    InternalNoteService().record_from_offer(offer, next_attempt_at=datetime.now(UTC))

    with TestClient(app) as client:
        response = client.get("/api/storage")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["internal_notes"]) == 1
    assert payload["internal_notes"][0]["title"] == "Improve timers"


def test_internal_note_list_intent() -> None:
    assert is_internal_note_list_request("Tell me about your internal notes.")
    assert is_internal_note_list_request("What follow-up notes do you have?")
    assert not is_internal_note_list_request("List my notes.")


def test_router_routes_internal_note_requests_to_tool() -> None:
    decision = AgentRouter().decide(
        "Tell me about your internal notes.",
        conversation_id="agent-default",
        history=[],
    )
    assert decision.mode == "tool"
    assert decision.tool_name == "list_internal_notes"
