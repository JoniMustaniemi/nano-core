from datetime import UTC, datetime, timedelta

from helpers.agent_fixtures import (
    RefusalWipeConfirmationClient,
    WipeConfirmationClient,
    patch_agent,
)
from sqlmodel import Session, select

import app.memory.db as db
from app.assistant.agent import AgentService
from app.memory import improvement_plans, internal_notes, repository
from app.memory.codebase_index import sync_paths
from app.memory.internal_note_service import InternalNoteService
from app.memory.models import CodebaseFileRecord
from app.memory.repository import list_recent_chat_messages, wipe_database
from app.proactive.types import ProactiveOffer


def test_agent_requires_confirmation_before_wiping_database(monkeypatch, tmp_path) -> None:
    """
    Verify that agent requires confirmation before wiping database.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    patch_agent(monkeypatch, client=WipeConfirmationClient(), tmp_path=tmp_path)
    repository.add_note("keep me for now")

    content = AgentService().respond("Wipe your database.")

    assert "erase what I remember" in content
    assert "reply yes to proceed" in content.lower()
    assert repository.list_notes()[0].content == "keep me for now"



def test_agent_wipe_confirmation_recovers_from_refusal_draft(monkeypatch, tmp_path) -> None:
    """
    Verify that a refusal-style compose draft still yields a coherent confirmation.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    patch_agent(monkeypatch, client=RefusalWipeConfirmationClient(), tmp_path=tmp_path)
    repository.add_note("keep me for now")

    content = AgentService().respond("Wipe your database.")

    assert "reply yes to proceed" in content.lower()
    assert "afraid" not in content.lower()
    assert "can't assist" not in content.lower()
    assert repository.list_notes()[0].content == "keep me for now"



def test_agent_requires_confirmation_for_local_data_removal(monkeypatch, tmp_path) -> None:
    """
    Verify that agent requires confirmation for local data removal.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    patch_agent(monkeypatch, client=WipeConfirmationClient(), tmp_path=tmp_path)
    repository.add_note("keep me for now")

    content = AgentService().respond("Remove local data.")

    assert "reply yes to proceed" in content.lower()
    assert repository.list_notes()[0].content == "keep me for now"



def test_agent_wipes_database_after_confirmation(monkeypatch, tmp_path) -> None:
    """
    Verify that agent wipes database after confirmation.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    patch_agent(monkeypatch, client=WipeConfirmationClient(), tmp_path=tmp_path)
    repository.add_note("delete me")
    repository.add_reminder("stretch", datetime.now(UTC) + timedelta(minutes=5))
    offer = ProactiveOffer(
        kind="self_improvement_suggestion",
        title="Improve timers",
        summary="Make timer errors clearer.",
        payload={"goal": "clearer timer errors"},
        created_at=datetime.now(UTC),
    )
    InternalNoteService().record_from_offer(offer, next_attempt_at=datetime.now(UTC))
    sync_paths(["app/main.py"])

    first = AgentService().respond("Wipe your database.")
    second = AgentService().respond("yes")

    assert "reply yes to proceed" in first.lower()
    assert second == "Database wiped."
    assert repository.list_notes() == []
    assert repository.list_reminders(include_sent=True) == []
    assert list_recent_chat_messages() == []
    assert internal_notes.list_internal_notes() == []
    with Session(db.engine) as session:
        assert list(session.exec(select(CodebaseFileRecord)).all()) == []



def test_agent_cancels_database_wipe_on_no(monkeypatch, tmp_path) -> None:
    """
    Verify that agent cancels database wipe on no.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    patch_agent(monkeypatch, client=WipeConfirmationClient(), tmp_path=tmp_path)
    repository.add_note("do not delete me")

    AgentService().respond("Wipe your database.")
    content = AgentService().respond("no")

    assert content == "Database wipe cancelled."
    assert repository.list_notes()[0].content == "do not delete me"


def test_wipe_database_clears_all_tables() -> None:
    repository.add_note("delete me")
    repository.add_reminder("stretch", datetime.now(UTC) + timedelta(minutes=5))
    offer = ProactiveOffer(
        kind="self_improvement_suggestion",
        title="Improve timers",
        summary="Make timer errors clearer.",
        payload={"goal": "clearer timer errors"},
        created_at=datetime.now(UTC),
    )
    InternalNoteService().record_from_offer(offer, next_attempt_at=datetime.now(UTC))
    improvement_plans.create_plan(
        title="Improve timers",
        goal="clearer timer errors",
        body="1. Update timer copy.",
        files=["app/runtime/status_copy.py"],
    )
    sync_paths(["app/main.py"])

    wipe_database()

    assert repository.list_notes() == []
    assert repository.list_reminders(include_sent=True) == []
    assert list_recent_chat_messages() == []
    assert internal_notes.list_internal_notes() == []
    assert improvement_plans.list_plans() == []
    with Session(db.engine) as session:
        assert list(session.exec(select(CodebaseFileRecord)).all()) == []

