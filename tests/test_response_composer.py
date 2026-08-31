import json

from app.assistant.response_composer import ResponseComposer
from app.assistant.response_source import (
    confirmation_source,
    follow_up_source,
    tool_result_source,
)
from app.runtime.status_copy import TIMER_DURATION_PROMPT


class _StubClient:
    def __init__(self, response: str = "Composed reply.") -> None:
        self.response = response
        self.messages = None

    def complete(self, messages) -> str:
        self.messages = messages
        return self.response


def test_compose_health_result_all_clear() -> None:
    composer = ResponseComposer()
    payload = json.dumps(
        {
            "overall": "ok",
            "checks": [
                {"name": "database", "status": "ok", "detail": "Database is reachable."},
            ],
        }
    )
    source = tool_result_source(
        user_message="Check your health.",
        facts=payload,
        tool_name="check_health",
        conversation_id="default",
    )

    content = composer.compose(_StubClient(), source)

    assert content == "My diagnostics are clear. No issues were found."


def test_compose_confirmation_uses_follow_up_text() -> None:
    composer = ResponseComposer()
    source = follow_up_source(
        user_message="Start a timer.",
        facts=TIMER_DURATION_PROMPT,
        conversation_id="default",
    )

    content = composer.compose(_StubClient(), source)

    assert content == TIMER_DURATION_PROMPT


def test_compose_wipe_confirmation_includes_yes_no_prompt() -> None:
    composer = ResponseComposer()
    source = confirmation_source(
        user_message="Wipe your database.",
        facts='User requested: "Wipe your database."',
        conversation_id="default",
        confirmation_action="wipe",
    )
    client = _StubClient(response="You want me to erase what I remember.")

    content = composer.compose(client, source)

    assert client.messages is None
    assert "say yes" in content.lower()
    assert "no" in content.lower()


def test_compose_wipe_confirmation_uses_deterministic_prompt() -> None:
    composer = ResponseComposer()
    source = confirmation_source(
        user_message="Wipe your database.",
        facts='User requested: "Wipe your database."',
        conversation_id="default",
        confirmation_action="wipe",
    )
    client = _StubClient(response="I'm afraid I can't assist with that.")

    content = composer.compose(client, source)

    assert client.messages is None
    assert "say yes" in content.lower()
    assert "afraid" not in content.lower()
    assert "wipe your database" in content.lower()


def test_compose_reboot_confirmation_is_deterministic() -> None:
    composer = ResponseComposer()
    source = confirmation_source(
        user_message="Reboot the Raspberry Pi.",
        facts='User requested: "Reboot the Raspberry Pi."',
        conversation_id="default",
        confirmation_action="reboot",
    )
    client = _StubClient(response="I'm ready. I wasn't restarted. I create the branch.")

    content = composer.compose(client, source)

    assert client.messages is None
    assert "reboot" in content.lower()
    assert "create the branch" not in content.lower()
    assert "yes" in content.lower()
    assert "no" in content.lower()
