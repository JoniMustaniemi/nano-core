from types import SimpleNamespace

from app.assistant.answer_executor import AnswerExecutor
from app.assistant.identity_context import (
    count_prior_identity_questions_in_history,
    format_identity_payload,
)
from app.assistant.rules.intents import is_identity_question


class _StubClient:
    def __init__(self, response: str = "I am Nano, your clinical overseer.") -> None:
        self.response = response
        self.messages = None

    def complete(self, messages) -> str:
        self.messages = messages
        return self.response


def test_is_identity_question_detects_intro_requests() -> None:
    assert is_identity_question("Who are you?")
    assert is_identity_question("Please introduce yourself.")
    assert is_identity_question("What are you?")
    assert not is_identity_question("What can you do?")


def test_count_prior_identity_questions_in_history() -> None:
    history = [
        SimpleNamespace(role="user", content="Who are you?"),
        SimpleNamespace(role="assistant", content="I am Nano."),
        SimpleNamespace(role="user", content="Who are you again?"),
    ]

    assert count_prior_identity_questions_in_history(history) == 1


def test_format_identity_payload_includes_variation_and_repeat_context() -> None:
    history = [
        SimpleNamespace(role="user", content="Who are you?"),
        SimpleNamespace(role="assistant", content="I am Nano."),
        SimpleNamespace(role="user", content="Introduce yourself."),
    ]
    payload = format_identity_payload(message="Introduce yourself.", history=history)

    assert "Core identity facts:" in payload
    assert "Registered capability names:" in payload
    assert "asked about your identity before" in payload
    assert "Variation guidance:" in payload


def test_draft_identity_uses_dynamic_payload() -> None:
    client = _StubClient()
    executor = AnswerExecutor()

    source = executor.draft_identity(
        client=client,
        message="Who are you?",
        conversation_id="default",
        history=[],
    )

    assert source.facts == "I am Nano, your clinical overseer."
    assert client.messages is not None
    assert "Core identity facts:" in client.messages[-1]["content"]
    assert "Variation guidance:" in client.messages[-1]["content"]
