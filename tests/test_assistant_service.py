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


class _ThirdPersonChatClient:
    def __init__(self) -> None:
        """
        Initialize the _ThirdPersonChatClient instance.

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
            return "Nano is ready."
        return "I am ready."


class _UnknownPersonChatClient:
    def __init__(self) -> None:
        """
        Initialize the _UnknownPersonChatClient instance.

        Returns:
            None.
        """
        self.calls = 0
        self.messages = []

    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        self.calls += 1
        self.messages.append(messages)
        if self.calls == 1:
            return "I'm Nano, a private local assistant."
        return "No reliable file in the mental cabinet for that person. How inconvenient."


class _ApologyDisclaimerChatClient:
    def __init__(self) -> None:
        """
        Initialize the _ApologyDisclaimerChatClient instance.

        Returns:
            None.
        """
        self.calls = 0
        self.messages = []

    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        self.calls += 1
        self.messages.append(messages)
        if self.calls == 1:
            return (
                "I apologize, but I don't have access to external databases "
                "or the internet for real-time information."
            )
        return "No confirmed entry emerges. The evidence remains theatrically absent."


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


def test_chat_mode_rewrites_third_person_self_reference(monkeypatch) -> None:
    """
    Verify that chat mode revises third-person self-reference.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.
    """
    client = _ThirdPersonChatClient()

    monkeypatch.setattr("app.assistant.service.get_llm_client", lambda: client)
    monkeypatch.setattr(
        "app.assistant.service.get_settings",
        lambda: SimpleNamespace(
            chat_history_limit=12,
            note_context_limit=5,
        ),
    )

    response = AssistantService().respond("status", mode="chat")

    assert response.content == "I am ready."
    assert client.calls == 2


def test_chat_mode_handles_unknown_fact_with_personality(monkeypatch) -> None:
    """
    Verify that unknown factual questions do not get a self-description answer.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.
    """
    client = _UnknownPersonChatClient()

    monkeypatch.setattr("app.assistant.service.get_llm_client", lambda: client)
    monkeypatch.setattr(
        "app.assistant.service.get_settings",
        lambda: SimpleNamespace(
            chat_history_limit=12,
            note_context_limit=5,
        ),
    )

    response = AssistantService().respond("Who is Jake Blamey?", mode="chat")

    assert response.content == "No reliable file in the mental cabinet for that person. How inconvenient."
    assert client.calls == 2
    assert "personality-driven" in client.messages[1][0]["content"]


def test_chat_mode_rewrites_apology_disclaimer(monkeypatch) -> None:
    """
    Verify that chat mode rewrites apology disclaimers in missing information answers.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.
    """
    client = _ApologyDisclaimerChatClient()

    monkeypatch.setattr("app.assistant.service.get_llm_client", lambda: client)
    monkeypatch.setattr(
        "app.assistant.service.get_settings",
        lambda: SimpleNamespace(
            chat_history_limit=12,
            note_context_limit=5,
        ),
    )

    response = AssistantService().respond("Who is Jake Blamey?", mode="chat")

    assert response.content == "No confirmed entry emerges. The evidence remains theatrically absent."
    assert client.calls == 2
    assert "missing evidence" in client.messages[1][0]["content"]


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
