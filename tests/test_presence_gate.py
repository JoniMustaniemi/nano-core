from datetime import UTC, datetime, timedelta

from app.assistant.flows.presence_gate import PresenceGateHandler
from app.assistant.pending import pending_interactions
from app.config import get_settings
from app.memory.db import create_db_and_tables
from app.memory.internal_note_service import InternalNoteService
from app.proactive.store import proactive_store
from app.proactive.types import ProactiveOffer
from app.runtime.status_copy import PRESENCE_TIMEOUT_TITLE


class _FakeClient:
    def complete(self, messages) -> str:
        return "I found an improvement idea."


def test_presence_gate_yes_delivers(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'pg.sqlite3'}")
    create_db_and_tables()
    get_settings.cache_clear()

    offer = ProactiveOffer(
        kind="self_improvement_suggestion",
        title="Improve timers",
        summary="Make timer errors clearer.",
        payload={"goal": "clearer timer errors"},
        created_at=datetime.now(UTC),
    )
    note = InternalNoteService().record_from_offer(offer, next_attempt_at=datetime.now(UTC))
    handler = PresenceGateHandler()
    proactive_store.reset()
    pending_interactions.reset()
    handler.start(offer, internal_note_id=note.id, conversation_id="agent-default")

    source = handler.handle_pending(
        message="yes",
        conversation_id="agent-default",
        client=_FakeClient(),
    )
    assert source is not None
    assert "pull request" in source.facts.lower()
    assert pending_interactions.get("agent-default") is None


def test_presence_gate_timeout_defers(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'pg2.sqlite3'}")
    create_db_and_tables()
    get_settings.cache_clear()

    offer = ProactiveOffer(
        kind="self_improvement_suggestion",
        title="Improve timers",
        summary="Make timer errors clearer.",
        payload={"goal": "clearer timer errors"},
        created_at=datetime.now(UTC),
    )
    handler = PresenceGateHandler()
    proactive_store.reset()
    pending_interactions.reset()
    handler.start(offer, conversation_id="agent-default")

    pending = pending_interactions.get("agent-default")
    assert pending is not None
    pending.payload["presence_started_at"] = (
        datetime.now(UTC) - timedelta(seconds=120)
    ).isoformat()
    pending_interactions.set(
        conversation_id="agent-default",
        kind="presence_check",
        payload=pending.payload,
    )

    handler.handle_timeout()
    snapshot = proactive_store.snapshot()
    assert snapshot["dismissal"] == PRESENCE_TIMEOUT_TITLE
    assert pending_interactions.get("agent-default") is None

    get_settings.cache_clear()
