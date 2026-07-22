from datetime import UTC, datetime, timedelta

from app.assistant.pending import pending_interactions
from app.config import get_settings
from app.memory.db import create_db_and_tables
from app.memory.internal_note_service import InternalNoteService
from app.proactive.background_tick import run_proactive_background_tick
from app.proactive.store import proactive_store
from app.proactive.types import ProactiveOffer
from app.runtime.activity import activity
from app.runtime.user_activity import user_activity


class _ExamineClient:
    def complete(self, messages) -> str:
        content = messages[-1]["content"]
        if "File index" in content:
            return '{"files_to_read": ["app/main.py"]}'
        return (
            '{"suggestion": "Improve startup logging.", '
            '"goal": "clearer startup logs", "confidence": "medium"}'
        )


def test_background_tick_outreach_requires_ten_minutes_idle(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tick.sqlite3'}")
    create_db_and_tables()
    get_settings.cache_clear()

    offer = ProactiveOffer(
        kind="self_improvement_suggestion",
        title="Improve timers",
        summary="Make timer errors clearer.",
        payload={"goal": "clearer timer errors"},
        created_at=datetime.now(UTC),
    )
    InternalNoteService().record_from_offer(offer, next_attempt_at=datetime.now(UTC))

    activity.reset()
    user_activity._last_activity_at = datetime.now(UTC) - timedelta(seconds=700)
    proactive_store.reset()
    pending_interactions.reset()

    monkeypatch.setattr(
        "app.proactive.background_tick.get_llm_client",
        lambda: _ExamineClient(),
    )
    started = {"called": False}

    def _start(*_args, **_kwargs):
        started["called"] = True
        proactive_store.start_presence()

    monkeypatch.setattr("app.proactive.background_tick.presence_gate.start", _start)

    run_proactive_background_tick()
    assert started["called"] is True
    assert proactive_store.snapshot()["waiting_for_presence"] is True

    get_settings.cache_clear()


def test_background_tick_skips_outreach_under_ten_minutes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tick2.sqlite3'}")
    create_db_and_tables()
    get_settings.cache_clear()

    offer = ProactiveOffer(
        kind="self_improvement_suggestion",
        title="Improve timers",
        summary="Make timer errors clearer.",
        payload={"goal": "clearer timer errors"},
        created_at=datetime.now(UTC),
    )
    InternalNoteService().record_from_offer(offer, next_attempt_at=datetime.now(UTC))

    activity.reset()
    proactive_store.reset()
    pending_interactions.reset()

    started = {"called": False}

    def _start(*_args, **_kwargs):
        started["called"] = True

    monkeypatch.setattr("app.proactive.background_tick.presence_gate.start", _start)

    user_activity._last_activity_at = datetime.now(UTC) - timedelta(seconds=200)
    run_proactive_background_tick()
    assert started["called"] is False

    get_settings.cache_clear()
