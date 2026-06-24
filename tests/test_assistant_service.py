from types import SimpleNamespace

from app.assistant.service import AssistantService


class _CapabilityEchoThenAnswerClient:
    def __init__(self) -> None:
        """
        Initialize the _CapabilityEchoThenAnswerClient instance.

        Returns:
            None.
        """
        self.calls = 0

    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
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


class _WakeResponseClient:
    def __init__(self) -> None:
        """
        Initialize the _WakeResponseClient instance.

        Returns:
            None.
        """
        self.messages = None

    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        self.messages = messages
        return "I am listening. Try to make this worth the interruption."


def test_chat_mode_retries_when_model_echoes_capabilities(monkeypatch) -> None:
    """
    Verify that chat mode retries when model echoes capabilities.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.
    """
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


def test_wake_response_uses_personality_prompt(monkeypatch) -> None:
    """
    Verify that wake response uses personality prompt.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.
    """
    client = _WakeResponseClient()

    monkeypatch.setattr("app.assistant.service.get_llm_client", lambda: client)

    response = AssistantService().wake_response()

    assert response.content == "I am listening. Try to make this worth the interruption."
    assert "wake phrase" in client.messages[0]["content"].lower()
    assert "one short sentence" in client.messages[0]["content"].lower()
