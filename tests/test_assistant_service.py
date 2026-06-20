from types import SimpleNamespace

from app.assistant.service import AssistantService


class _CapabilityEchoThenAnswerClient:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages) -> str:
        self.calls += 1
        if self.calls == 1:
            return (
                "I'm Nano, a private local assistant. I can execute local Python code, "
                "read and write text files, list files, add notes, list notes, add "
                "reminders, and list reminders."
            )
        return (
            "Rocks form in different ways, including igneous, sedimentary, and "
            "metamorphic processes."
        )


def test_chat_mode_retries_when_model_echoes_capabilities(monkeypatch) -> None:
    client = _CapabilityEchoThenAnswerClient()

    monkeypatch.setattr("app.assistant.service.get_llm_client", lambda: client)
    monkeypatch.setattr(
        "app.assistant.service.get_settings",
        lambda: SimpleNamespace(
            chat_history_limit=12,
            note_context_limit=5,
        ),
    )

    response = AssistantService().respond("tell me about rocks", mode="chat")

    assert "Rocks form in different ways" in response.content
    assert client.calls == 2
