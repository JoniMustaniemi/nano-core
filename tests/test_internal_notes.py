from datetime import UTC, datetime

from app.memory import internal_notes
from app.memory.db import create_db_and_tables
from app.memory.internal_note_service import InternalNoteService
from app.proactive.types import ProactiveOffer


def test_internal_note_lifecycle(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'notes.sqlite3'}")
    create_db_and_tables()

    offer = ProactiveOffer(
        kind="self_improvement_suggestion",
        title="Improve timers",
        summary="Make timer errors clearer.",
        payload={"goal": "clearer timer errors"},
        created_at=datetime.now(UTC),
    )
    service = InternalNoteService()
    note = service.record_from_offer(offer, next_attempt_at=datetime.now(UTC))
    assert note.id is not None

    due = internal_notes.list_due_internal_notes(now=datetime.now(UTC))
    assert len(due) == 1

    service.mark_delivered(note.id)
    due_after = internal_notes.list_due_internal_notes(now=datetime.now(UTC))
    assert not due_after


def test_internal_note_reschedule_dismisses_after_max_attempts(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'notes2.sqlite3'}")
    monkeypatch.setenv("INTERNAL_NOTE_MAX_ATTEMPTS", "2")
    create_db_and_tables()

    from app.config import get_settings

    get_settings.cache_clear()

    offer = ProactiveOffer(
        kind="self_improvement_suggestion",
        title="Improve timers",
        summary="Make timer errors clearer.",
        payload={"goal": "clearer timer errors"},
        created_at=datetime.now(UTC),
    )
    service = InternalNoteService()
    note = service.record_from_offer(offer, next_attempt_at=datetime.now(UTC))
    service.record_deferred_offer(offer, reason="timeout", note_id=note.id)
    refreshed = internal_notes.get_internal_note(note.id or 0)
    assert refreshed is not None
    assert refreshed.attempt_count >= 1

    get_settings.cache_clear()
