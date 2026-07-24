from datetime import UTC, datetime, timedelta

from app.assistant.flows.presence_gate import PresenceGateHandler
from app.assistant.pending import pending_interactions
from app.config import get_settings
from app.memory import improvement_plans
from app.memory.db import create_db_and_tables
from app.memory.internal_note_service import InternalNoteService
from app.proactive.store import proactive_store
from app.proactive.types import ProactiveOffer
from app.runtime.status_copy import PRESENCE_TIMEOUT_TITLE


class _DraftClient:
    def complete(self, messages, **kwargs) -> str:
        content = messages[-1]["content"]
        if "Known files:" in content:
            return '{"files_to_read": ["app/main.py"]}'
        return (
            "Summary\n"
            "Clearer timer errors.\n"
            "Target file\n"
            "app/main.py\n"
            "Proposed change\n"
            "- Improve error copy.\n"
        )


def test_presence_gate_yes_delivers(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'pg.sqlite3'}")
    create_db_and_tables()
    get_settings.cache_clear()
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("value = 1\n", encoding="utf-8")

    offer = ProactiveOffer(
        kind="self_improvement_suggestion",
        title="Improve timers",
        summary="Make timer errors clearer.",
        payload={"goal": "clearer timer errors", "files": ["app/main.py"]},
        created_at=datetime.now(UTC),
    )
    note = InternalNoteService().record_from_offer(offer, next_attempt_at=datetime.now(UTC))
    handler = PresenceGateHandler()
    proactive_store.reset()
    pending_interactions.reset()
    handler.start(offer, internal_note_id=note.id, conversation_id="agent-default")

    monkeypatch.setattr(
        "app.tools.self_improve_planning.file_selection_lines",
        lambda goal, limit=40: ["- app/main.py: Main entrypoint."],
    )

    source = handler.handle_pending(
        message="yes",
        conversation_id="agent-default",
        client=_DraftClient(),
    )
    assert source is not None
    assert "plans tab" in source.facts.lower()
    assert pending_interactions.get("agent-default") is None
    assert improvement_plans.has_unprocessed_plan() is True
    plan = improvement_plans.get_unprocessed_plan()
    assert plan is not None
    assert plan.goal == "clearer timer errors"


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
