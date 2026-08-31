from types import SimpleNamespace

from helpers.agent_fixtures import (
    InvalidThenChatClient,
    IrrelevantToolThenFinalClient,
    NeverFinishesClient,
    RunPythonClient,
    agent_respond,
    patch_agent,
)

from app.memory import repository
from app.runtime.status_copy import CONFUSED_RESPONSES


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

    content = agent_respond("What is 2 + 2?")

    assert content == "The result is 4."
    assert client.calls >= 2
    assert "never refer to yourself by name" in client.messages[0]["content"].lower()


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
        announce=lambda text: announcements.append(text),
    )

    agent_respond("What is 2 + 2?")

    assert announcements == ["Running a local procedure"]


def test_agent_falls_back_to_confused_when_model_skips_json(monkeypatch, tmp_path) -> None:
    """
    Verify that agent returns a confused response when the model never returns valid JSON.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = InvalidThenChatClient()
    patch_agent(monkeypatch, client=client, tmp_path=tmp_path)

    content = agent_respond("What's the weather?")

    assert content in CONFUSED_RESPONSES
    assert client.calls >= 2


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
        announce=lambda text: None,
    )

    content = agent_respond("What's the weather?")

    assert content in CONFUSED_RESPONSES
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
        announce=lambda text: announcements.append(text),
    )
    monkeypatch.setattr(
        "app.assistant.tool_runner.get_tool",
        lambda name: SimpleNamespace(
            name=name,
            handler=lambda args: (_ for _ in ()).throw(RuntimeError("boom")),
        ),
    )

    content = agent_respond("What is 2 + 2?")

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
        announce=lambda text: announcements.append(text),
    )

    content = agent_respond("What is 2 + 2?")

    assert content == "I tried to complete the task, but I hit the step limit."
    assert announcements[-1] == "I could not finish the task."


class AnswerIntentNoToolClient:
    def complete(self, messages) -> str:
        return '{"type":"final","content":"Some prose answer without running a tool."}'


def test_agent_returns_confused_when_planner_finishes_without_tools(
    monkeypatch,
    tmp_path,
) -> None:
    client = AnswerIntentNoToolClient()
    patch_agent(monkeypatch, client=client, tmp_path=tmp_path)

    content = agent_respond("What's the weather?")

    assert content in CONFUSED_RESPONSES
    assert "prose answer" not in content.lower()
