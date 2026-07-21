from app.assistant.agent import AgentService
from app.memory import repository
from helpers.agent_fixtures import (
    ApologyDisclaimerClient,
    CapabilityQuestionClient,
    ContinuationFinalClient,
    ThirdPersonFinalClient,
    UnknownPersonSelfDescriptionClient,
    patch_agent,
)


def test_agent_rewrites_third_person_final_answer(monkeypatch, tmp_path) -> None:
    """
    Verify that agent rewrites third-person self-reference in final answers.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = ThirdPersonFinalClient()
    patch_agent(monkeypatch, client=client, tmp_path=tmp_path)

    content = AgentService().respond("How are you?")

    assert content == "I am operating normally."
    assert client.calls == 2
    assert "rewrite it so you speak as nano in first person" in (
        client.messages[1][0]["content"].lower()
    )



def test_agent_rewrites_self_description_for_unknown_fact_question(
    monkeypatch,
    tmp_path,
) -> None:
    """
    Verify that unknown factual questions do not fall back to self-description.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = UnknownPersonSelfDescriptionClient()
    patch_agent(monkeypatch, client=client, tmp_path=tmp_path)

    content = AgentService().respond("Who is Jake Blamey?")

    assert content == "No usable record surfaced for that name. A tragic shortage of evidence."
    assert client.calls == 2
    assert "personality-driven" in client.messages[1][0]["content"]
    assert "I am Nano" in client.messages[1][1]["content"]



def test_agent_rewrites_apology_disclaimer_for_missing_information(
    monkeypatch,
    tmp_path,
) -> None:
    """
    Verify that missing information answers do not apologize or use generic disclaimers.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = ApologyDisclaimerClient()
    patch_agent(monkeypatch, client=client, tmp_path=tmp_path)

    content = AgentService().respond("Who is Jake Blamey?")

    assert (
        content
        == "No verified record presents itself. Evidently the archive declined to cooperate."
    )
    assert client.calls == 2
    assert "Do not apologize" in client.messages[1][0]["content"]
    assert "I apologize" in client.messages[1][1]["content"]



def test_agent_rewrites_unsupported_continuation_promise(monkeypatch, tmp_path) -> None:
    """
    Verify that final answers do not promise unsupported continued work.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = ContinuationFinalClient()
    patch_agent(monkeypatch, client=client, tmp_path=tmp_path)

    content = AgentService().respond("Check the situation.")

    assert content == "Current result only: no ongoing work is running."
    assert client.calls == 2
    assert "Do not tell the user to wait for more results" in client.messages[1][0]["content"]



def test_agent_answers_capability_questions_without_tool_use(monkeypatch, tmp_path) -> None:
    """
    Verify that agent answers capability questions without tool use.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = CapabilityQuestionClient()
    patch_agent(monkeypatch, client=client, tmp_path=tmp_path)

    content = AgentService().respond("What can you do?")

    assert "I can answer questions" in content
    assert client.calls == 1
    assert repository.list_reminders() == []


