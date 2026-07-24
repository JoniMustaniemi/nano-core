from types import SimpleNamespace

from helpers.agent_fixtures import (
    InvalidThenChatClient,
    IrrelevantToolThenFinalClient,
    NeverFinishesClient,
    RunPythonClient,
    patch_agent,
)

from app.assistant.agent import AgentService
from app.memory import repository


def test_agent_runs_a_legitimate_tool_call(monkeypatch, tmp_path) -> None:
    """
    Verify that agent runs a legitimate tool call.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = RunPythonClient()
    patch_agent(monkeypatch, client=client, tmp_path=tmp_path)

    content = AgentService().respond("What is 2 + 2?")

    assert content == "The result is 4."
    assert client.calls >= 2
    assert "never refer to nano in third person" in client.messages[0]["content"].lower()


def test_agent_announces_tool_calls(monkeypatch, tmp_path) -> None:
    """
    Verify that agent announces tool calls.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = RunPythonClient()
    announcements: list[str] = []
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: announcements.append(text),
    )

    AgentService().respond("What is 2 + 2?")

    assert announcements == ["Running a local procedure"]


def test_agent_falls_back_to_plain_chat_when_model_skips_json(monkeypatch, tmp_path) -> None:
    """
    Verify that agent falls back to plain chat when model skips json.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = InvalidThenChatClient()
    patch_agent(monkeypatch, client=client, tmp_path=tmp_path)

    content = AgentService().respond("hey nano")

    assert content == "Hello there"
    assert client.calls == 3


def test_agent_rejects_irrelevant_tool_calls(monkeypatch, tmp_path) -> None:
    """
    Verify that agent rejects irrelevant tool calls.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = IrrelevantToolThenFinalClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )

    content = AgentService().respond("Tell me about rocks.")

    assert "igneous" in content
    assert repository.list_timers() == []


def test_agent_announces_tool_errors(monkeypatch, tmp_path) -> None:
    """
    Verify that agent announces tool errors.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = RunPythonClient()
    announcements: list[str] = []
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: announcements.append(text),
    )
    monkeypatch.setattr(
        "app.assistant.tool_runner.get_tool",
        lambda name: SimpleNamespace(
            name=name,
            handler=lambda args: (_ for _ in ()).throw(RuntimeError("boom")),
        ),
    )

    content = AgentService().respond("What is 2 + 2?")

    assert content == "The result is 4."
    assert "I hit an error while trying to complete the task." in announcements


def test_agent_announces_step_limit_errors(monkeypatch, tmp_path) -> None:
    """
    Verify that agent announces step limit errors.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    announcements: list[str] = []
    patch_agent(
        monkeypatch,
        client=NeverFinishesClient(),
        tmp_path=tmp_path,
        announce=lambda self, text: announcements.append(text),
    )

    content = AgentService().respond("What is 2 + 2?")

    assert content == "I tried to complete the task, but I hit the step limit."
    assert announcements[-1] == "I could not finish the task."
