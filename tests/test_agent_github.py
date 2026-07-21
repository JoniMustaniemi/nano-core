import json
from types import SimpleNamespace

import pytest

from app.assistant.agent import AgentService
from app.assistant.agent_rules import is_pull_request_request
from app.memory.repository import list_recent_chat_messages


def test_is_pull_request_request_matches_common_phrases() -> None:
    assert is_pull_request_request("create a PR") is True
    assert is_pull_request_request("open a pull request") is True
    assert is_pull_request_request("what is a pull request") is False


def test_agent_routes_pull_request_request_directly(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class _Client:
        def complete(self, messages) -> str:
            return "I opened the pull request at https://github.com/org/repo/pull/1."

    monkeypatch.setattr("app.assistant.orchestrator.get_llm_client", lambda: _Client())
    monkeypatch.setattr(
        "app.assistant.orchestrator.get_settings",
        lambda: SimpleNamespace(chat_history_limit=12, workspace_root="."),
    )
    monkeypatch.setattr(
        "app.assistant.tool_runner.GladosVoiceService.announce",
        lambda self, text: calls.append(text),
    )
    monkeypatch.setattr(
        "app.tools.github_tools.PullRequestService",
        lambda: SimpleNamespace(
            run=lambda client: SimpleNamespace(
                to_json=lambda: json.dumps(
                    {
                        "ok": True,
                        "step": "complete",
                        "url": "https://github.com/org/repo/pull/1",
                        "branch": "feature/add_github_pr",
                        "title": "add_github_pr",
                        "base": "main",
                        "verified_with": "python -m pytest -q",
                        "error": None,
                        "output": None,
                    }
                )
            )
        ),
    )

    response = AgentService().respond("create a pull request")

    assert "http" not in response
    assert "Review it on GitHub when you are ready." in response
    messages = list_recent_chat_messages(limit=2)
    assert messages[-1].role == "assistant"
    assert messages[-1].content == response
