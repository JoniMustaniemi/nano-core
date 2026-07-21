from helpers.agent_fixtures import ShouldNotBeCalledClient, patch_agent

from app.assistant.agent import AgentService
from app.assistant.pending import pending_interactions
from app.memory import repository


def test_agent_asks_for_note_content_before_using_model(monkeypatch, tmp_path) -> None:
    """
    Verify that note requests without content ask for the note.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    patch_agent(monkeypatch, client=ShouldNotBeCalledClient(), tmp_path=tmp_path)

    content = AgentService().respond("Add a note.")

    assert content == "What should I call this note?"
    assert repository.list_notes() == []
    assert pending_interactions.get("default") is not None



def test_agent_saves_note_after_name_and_content_follow_up(monkeypatch, tmp_path) -> None:
    """
    Verify that pending note content is saved.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    patch_agent(monkeypatch, client=ShouldNotBeCalledClient(), tmp_path=tmp_path)

    first = AgentService().respond("Add note.")
    second = AgentService().respond("Shopping")
    third = AgentService().respond("Buy milk.")
    notes = repository.list_notes()

    assert first == "What should I call this note?"
    assert second == "What should I remember under Shopping?"
    assert third == "Saved note #1: Shopping."
    assert [note.name for note in notes] == ["Shopping"]
    assert [note.content for note in notes] == ["Buy milk."]
    assert pending_interactions.get("default") is None



def test_agent_asks_for_name_before_saving_inline_note(monkeypatch, tmp_path) -> None:
    """
    Verify that note content in the initial request is saved.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    patch_agent(monkeypatch, client=ShouldNotBeCalledClient(), tmp_path=tmp_path)

    first = AgentService().respond("Remember that the launch code is tea.")
    second = AgentService().respond("Launch code")
    notes = repository.list_notes()

    assert first == "What should I call this note?"
    assert second == "Saved note #1: Launch code."
    assert [note.name for note in notes] == ["Launch code"]
    assert [note.content for note in notes] == ["the launch code is tea."]



def test_agent_lists_saved_notes_without_model(monkeypatch, tmp_path) -> None:
    """
    Verify that saved notes can be retrieved.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    patch_agent(monkeypatch, client=ShouldNotBeCalledClient(), tmp_path=tmp_path)
    repository.add_note("Buy milk.", name="Shopping")
    repository.add_note("Check the air filter.", name="Maintenance")

    content = AgentService().respond("What do you remember?")

    assert "Here is what I remember:" in content
    assert "- Shopping: Buy milk." in content
    assert "- Maintenance: Check the air filter." in content



def test_agent_cancels_pending_note_request(monkeypatch, tmp_path) -> None:
    """
    Verify that pending note requests can be cancelled.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = ShouldNotBeCalledClient()
    patch_agent(monkeypatch, client=client, tmp_path=tmp_path)

    for rejection in ("cancel", "nothing", "stop"):
        first = AgentService().respond("Add note.")
        second = AgentService().respond(rejection)

        assert first == "What should I call this note?"
        assert second == "Note cancelled."
        assert pending_interactions.get("default") is None

    assert repository.list_notes() == []



def test_agent_finds_single_note_by_keyword(monkeypatch, tmp_path) -> None:
    """
    Verify that memory-shaped questions search saved notes by keyword.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    patch_agent(monkeypatch, client=ShouldNotBeCalledClient(), tmp_path=tmp_path)
    repository.add_note("hunter2", name="Password")

    content = AgentService().respond("Hey Nano what was my password?")

    assert content == "I found note Password: hunter2"



def test_agent_asks_which_note_when_multiple_keyword_matches(monkeypatch, tmp_path) -> None:
    """
    Verify that multiple keyword matches ask for note selection.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    patch_agent(monkeypatch, client=ShouldNotBeCalledClient(), tmp_path=tmp_path)
    repository.add_note("work-password-1", name="Work password")
    repository.add_note("bank-password-2", name="Bank password")

    first = AgentService().respond("What was my password?")
    second = AgentService().respond("Bank password")

    assert "I found multiple matching notes:" in first
    assert "1. Bank password" in first
    assert "2. Work password" in first
    assert first.endswith("Which one?")
    assert second == "I found note Bank password: bank-password-2"


