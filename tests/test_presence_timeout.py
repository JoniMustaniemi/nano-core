from datetime import UTC, datetime

from app.assistant.pending import pending_interactions
from app.common.types import ProactiveOffer
from app.config import get_settings
from app.proactive.background_tick import check_presence_timeouts
from app.proactive.store import proactive_store
from app.runtime.status_copy import PRESENCE_TIMEOUT_TITLE


def _start_presence_check(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.assistant.flows.presence_gate.internal_note_service.record_deferred_offer",
        lambda *args, **kwargs: None,
    )
    proactive_store.set_offer(
        ProactiveOffer(
            kind="self_improvement_suggestion",
            title="Improve timers",
            summary="Make timer errors clearer.",
            payload={"goal": "clearer timer errors"},
            created_at=datetime.now(UTC),
        )
    )


def test_check_presence_timeouts_expires_malformed_timestamp(monkeypatch) -> None:
    get_settings.cache_clear()
    proactive_store.reset()
    pending_interactions.reset()
    _start_presence_check(monkeypatch)

    pending_interactions.set(
        conversation_id=get_settings().proactive_conversation_id,
        kind="presence_check",
        payload={"presence_started_at": "not-a-timestamp"},
    )

    check_presence_timeouts()

    assert proactive_store.snapshot()["dismissal"] == PRESENCE_TIMEOUT_TITLE
    assert pending_interactions.get(get_settings().proactive_conversation_id) is None


def test_check_presence_timeouts_expires_missing_timestamp(monkeypatch) -> None:
    get_settings.cache_clear()
    proactive_store.reset()
    pending_interactions.reset()
    _start_presence_check(monkeypatch)

    pending_interactions.set(
        conversation_id=get_settings().proactive_conversation_id,
        kind="presence_check",
        payload={},
    )

    check_presence_timeouts()

    assert proactive_store.snapshot()["dismissal"] == PRESENCE_TIMEOUT_TITLE


def test_check_presence_timeouts_keeps_valid_recent_timestamp(monkeypatch) -> None:
    get_settings.cache_clear()
    proactive_store.reset()
    pending_interactions.reset()
    _start_presence_check(monkeypatch)

    pending_interactions.set(
        conversation_id=get_settings().proactive_conversation_id,
        kind="presence_check",
        payload={"presence_started_at": datetime.now(UTC).isoformat()},
    )

    check_presence_timeouts()

    assert proactive_store.snapshot()["dismissal"] is None
    assert pending_interactions.get(get_settings().proactive_conversation_id) is not None
