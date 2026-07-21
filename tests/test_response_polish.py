from app.assistant.response_polish import (
    looks_repetitive,
    polish_user_facing_answer,
    should_polish,
)
from app.assistant.response_source import answer_source, follow_up_source, tool_result_source


class _StubClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.messages = None

    def complete(self, messages) -> str:
        self.messages = messages
        return self.response


def test_looks_repetitive_detects_listy_capability_dump() -> None:
    content = (
        "I can add notes, reminders, timers, and notes, cancel timers, check health, "
        "initiate pull requests, list files, list notes, list reminders, list timers, "
        "clear storage, read files, run Python code, start timers, and write files."
    )

    assert looks_repetitive(content)


def test_should_polish_answer_kind() -> None:
    source = answer_source(
        user_message="What can you do?",
        facts="Draft.",
        conversation_id="default",
    )

    assert should_polish(source, "Short answer.")


def test_should_not_polish_follow_up() -> None:
    source = follow_up_source(
        user_message="Start a timer.",
        facts="How long should the timer run?",
        conversation_id="default",
    )

    assert not should_polish(source, "How long should the timer run?")


def test_polish_user_facing_answer_tightens_repetitive_draft() -> None:
    source = answer_source(
        user_message="What can you do?",
        facts="Draft.",
        conversation_id="default",
    )
    draft = (
        "I can add notes, reminders, timers, and notes, cancel timers, check health, "
        "list files, list notes, list reminders, list timers, read files, run Python, "
        "start timers, and write files."
    )
    client = _StubClient(
        "I handle notes, reminders, timers, local files, Python, diagnostics, and pull requests."
    )

    content = polish_user_facing_answer(client, source, draft)

    assert content == (
        "I handle notes, reminders, timers, local files, Python, diagnostics, and pull requests."
    )
    assert client.messages is not None
    assert "polishing nano's final reply" in client.messages[0]["content"].lower()


def test_polish_user_facing_answer_skips_clean_short_tool_result() -> None:
    source = tool_result_source(
        user_message="Check your health.",
        facts="My diagnostics are clear.",
        tool_name="check_health",
        conversation_id="default",
    )
    client = _StubClient("Should not be called.")

    content = polish_user_facing_answer(
        client,
        source,
        "My diagnostics are clear.",
    )

    assert content == "My diagnostics are clear."
    assert client.messages is None
