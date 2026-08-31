from datetime import UTC, datetime, timedelta

from helpers.agent_fixtures import (
    RefusalWipeConfirmationClient,
    WipeConfirmationClient,
    agent_respond,
    patch_agent,
)

from app.common.types import ProactiveOffer
from app.memory import internal_notes, repository
from app.memory.internal_note_service import InternalNoteService
from app.memory.repository import list_recent_chat_messages, wipe_database


def test_agent_requires_confirmation_before_wiping_database(monkeypatch, tmp_path) -> None:
    patch_agent(monkeypatch, client=WipeConfirmationClient(), tmp_path=tmp_path)
    repository.add_chat_message(conversation_id="default", role="user", content="keep me for now")

    content = agent_respond("Wipe your database.")

    assert "wipe your database" in content.lower()
    assert "yes" in content.lower()
    assert "no" in content.lower()
    assert list_recent_chat_messages()[0].content == "keep me for now"


def test_agent_wipe_confirmation_recovers_from_refusal_draft(monkeypatch, tmp_path) -> None:
    patch_agent(monkeypatch, client=RefusalWipeConfirmationClient(), tmp_path=tmp_path)
    repository.add_chat_message(conversation_id="default", role="user", content="keep me for now")

    content = agent_respond("Wipe your database.")

    assert "yes" in content.lower()
    assert "no" in content.lower()
    assert "afraid" not in content.lower()
    assert "can't assist" not in content.lower()
    assert list_recent_chat_messages()[0].content == "keep me for now"


def test_agent_requires_confirmation_for_local_data_removal(monkeypatch, tmp_path) -> None:
    patch_agent(monkeypatch, client=WipeConfirmationClient(), tmp_path=tmp_path)
    repository.add_chat_message(conversation_id="default", role="user", content="keep me for now")

    content = agent_respond("Remove local data.")

    assert "yes" in content.lower()
    assert "no" in content.lower()
    assert list_recent_chat_messages()[0].content == "keep me for now"


def test_agent_wipes_database_after_confirmation(monkeypatch, tmp_path) -> None:
    patch_agent(monkeypatch, client=WipeConfirmationClient(), tmp_path=tmp_path)
    repository.add_chat_message(conversation_id="default", role="user", content="delete me")
    repository.add_timer("stretch", datetime.now(UTC) + timedelta(minutes=5))
    offer = ProactiveOffer(
        kind="follow_up",
        title="Improve timers",
        summary="Make timer errors clearer.",
        payload={"goal": "clearer timer errors"},
        created_at=datetime.now(UTC),
    )
    InternalNoteService().record_from_offer(offer, next_attempt_at=datetime.now(UTC))

    first = agent_respond("Wipe your database.")
    second = agent_respond("yes")

    assert "say yes" in first.lower()
    assert second == "Database wiped."
    assert list_recent_chat_messages() == []
    assert repository.list_timers() == []
    assert internal_notes.list_internal_notes() == []


def test_agent_cancels_database_wipe_on_no(monkeypatch, tmp_path) -> None:
    patch_agent(monkeypatch, client=WipeConfirmationClient(), tmp_path=tmp_path)
    repository.add_chat_message(conversation_id="default", role="user", content="do not delete me")

    agent_respond("Wipe your database.")
    content = agent_respond("no")

    assert content == "Database wipe cancelled."
    assert list_recent_chat_messages()[0].content == "do not delete me"


def test_wipe_database_clears_all_tables() -> None:
    repository.add_chat_message(conversation_id="default", role="user", content="delete me")
    repository.add_timer("stretch", datetime.now(UTC) + timedelta(minutes=5))
    offer = ProactiveOffer(
        kind="follow_up",
        title="Improve timers",
        summary="Make timer errors clearer.",
        payload={"goal": "clearer timer errors"},
        created_at=datetime.now(UTC),
    )
    InternalNoteService().record_from_offer(offer, next_attempt_at=datetime.now(UTC))

    wipe_database()

    assert list_recent_chat_messages() == []
    assert repository.list_timers() == []
    assert internal_notes.list_internal_notes() == []
