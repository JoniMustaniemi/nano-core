import json

from app.assistant.response_composer import ResponseComposer
from app.assistant.response_source import (
    confirmation_source,
    follow_up_source,
    tool_error_source,
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


def test_compose_pr_result_success_is_voice_friendly() -> None:
    composer = ResponseComposer()
    payload = json.dumps(
        {
            "ok": True,
            "url": "https://example.com/pr/1",
            "branch": "feature/demo",
            "title": "demo change",
        }
    )
    source = tool_result_source(
        user_message="Create a PR",
        facts=payload,
        tool_name="create_pull_request",
        conversation_id="default",
    )
    client = _StubClient(response="Review it [here](https://example.com/pr/1).")

    content = composer.compose(client, source)

    assert content == ("I opened the pull request. Review it on GitHub when you are ready.")
    assert "http" not in content
    assert client.messages is None


def test_compose_pr_tool_error_skips_llm() -> None:
    composer = ResponseComposer()
    payload = json.dumps(
        {
            "ok": False,
            "step": "verify",
            "error": "Verification failed.",
            "output": "FAILED tests/test_example.py",
        }
    )
    source = tool_error_source(
        user_message="Open a PR",
        facts=payload,
        tool_name="create_pull_request",
        conversation_id="default",
    )
    client = _StubClient(response="Slow LLM reply.")

    content = composer.compose(client, source)

    assert content == (
        "Your tests failed, so I declined to commit anything or open a pull request."
    )
    assert client.messages is None


def test_compose_pr_lint_error_includes_checker_summary() -> None:
    composer = ResponseComposer()
    error = "Type checks failed: app/tools/demo.py:1: error: example"
    payload = json.dumps({"ok": False, "step": "lint", "error": error})
    source = tool_error_source(
        user_message="Open a PR",
        facts=payload,
        tool_name="create_pull_request",
        conversation_id="default",
    )

    content = composer.compose(_StubClient(), source)

    assert "demo.py" in content
    assert error in content


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
    )
    client = _StubClient(response="You want me to erase what I remember.")

    content = composer.compose(client, source)

    assert "say yes" in content.lower()
    assert "no" in content.lower()


def test_compose_wipe_confirmation_uses_fallback_for_refusal_draft() -> None:
    composer = ResponseComposer()
    source = confirmation_source(
        user_message="Wipe your database.",
        facts='User requested: "Wipe your database."',
        conversation_id="default",
    )
    client = _StubClient(response="I'm afraid I can't assist with that.")

    content = composer.compose(client, source)

    assert "say yes" in content.lower()
    assert "afraid" not in content.lower()
    assert "wipe your database" in content.lower()
