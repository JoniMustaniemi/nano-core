from datetime import UTC, datetime, timedelta

from app.assistant.agent import AgentService
from app.memory import repository
from app.memory.repository import list_recent_chat_messages
from helpers.agent_fixtures import WipeConfirmationClient, patch_agent


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

    first = AgentService().respond("Wipe your database.")
    second = AgentService().respond("yes")

    assert "reply yes to proceed" in first.lower()
    assert second == "Database wiped."
    assert repository.list_notes() == []
    assert repository.list_reminders(include_sent=True) == []
    assert list_recent_chat_messages() == []



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


