from types import SimpleNamespace

from app.assistant.agent import AgentService


class _SequencedClient:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages) -> str:
        self.calls += 1
        if self.calls == 1:
            return (
                '{"type":"tool_call","tool":"run_python","args":{"code":"print(2 + 2)"}}'
            )
        return '{"type":"final","content":"The result is 4."}'


def test_agent_mode_can_run_python(monkeypatch, tmp_path) -> None:
    client = _SequencedClient()

    monkeypatch.setattr("app.assistant.agent.get_llm_client", lambda: client)
    monkeypatch.setattr(
        "app.assistant.agent.get_settings",
        lambda: SimpleNamespace(
            chat_history_limit=12,
            workspace_root=str(tmp_path),
        ),
    )

    content = AgentService().respond("What is 2 + 2?")

    assert content == "The result is 4."
    assert client.calls >= 2
