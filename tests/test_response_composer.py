import json

from app.assistant.response_composer import ResponseComposer
from app.assistant.response_source import (
    follow_up_source,
    tool_error_source,
    tool_result_source,
)


class _SummaryClient:
    def __init__(self, response: str = "") -> None:
        self.response = response
        self.calls = 0
        self.messages = None

    def complete(self, messages) -> str:
        self.calls += 1
        self.messages = messages
        return self.response


def test_compose_pr_result_success_uses_llm() -> None:
    client = _SummaryClient(
        "I opened pull request fix_timer_cancel_bug at https://github.com/org/repo/pull/1."
    )
    composer = ResponseComposer()
    payload = json.dumps(
        {
            "ok": True,
            "step": "complete",
            "url": "https://github.com/org/repo/pull/1",
            "branch": "feature/fix_timer_cancel_bug",
            "title": "fix_timer_cancel_bug",
            "base": "main",
            "verified_with": "python -m pytest -q",
            "error": None,
            "output": None,
        }
    )
    source = tool_result_source(
        user_message="create a PR",
        facts=payload,
        tool_name="create_pull_request",
    )

    summary = composer.compose(client, source)

    assert "https://github.com/org/repo/pull/1" in summary
    assert client.calls == 1
    assert "never apologize" in client.messages[0]["content"].lower()


def test_compose_pr_result_failure_fallback() -> None:
    client = _SummaryClient("")
    composer = ResponseComposer()
    payload = json.dumps(
        {
            "ok": False,
            "step": "verify",
            "url": None,
            "branch": None,
            "title": None,
            "base": None,
            "verified_with": "python -m pytest -q",
            "error": "Verification failed.",
            "output": "FAILED tests/test_x.py",
        }
    )
    source = tool_result_source(
        user_message="create a PR",
        facts=payload,
        tool_name="create_pull_request",
    )

    summary = composer.compose(client, source)

    assert "declined to commit" in summary.lower()
    assert "FAILED tests/test_x.py" not in summary
    assert "sorry" not in summary.lower()
    assert "apolog" not in summary.lower()


def test_compose_health_result_is_deterministic() -> None:
    composer = ResponseComposer()
    payload = json.dumps(
        {
            "checks": [
                {"name": "voice", "status": "error", "detail": "Voice backend is unavailable."},
            ]
        }
    )
    source = tool_result_source(
        user_message="check your health",
        facts=payload,
        tool_name="check_health",
    )

    summary = composer.compose(_SummaryClient(), source)

    assert summary == "My voice check is failing: Voice backend is unavailable."


def test_compose_follow_up_passes_through() -> None:
    composer = ResponseComposer()
    source = follow_up_source(
        user_message="start a timer",
        facts="How long should the timer run?",
    )

    summary = composer.compose(_SummaryClient(), source)

    assert summary == "How long should the timer run?"


def test_compose_tool_error_uses_personality_prompt() -> None:
    client = _SummaryClient(
        "GitHub CLI authentication failed. Run `gh auth login`, then ask again."
    )
    composer = ResponseComposer()
    source = tool_error_source(
        user_message="create a PR",
        facts=json.dumps(
            {
                "ok": False,
                "error": "GitHub CLI is not authenticated.",
            }
        ),
        tool_name="create_pull_request",
    )

    summary = composer.compose(client, source)

    assert "gh auth login" in summary
    assert client.calls == 1
    assert "sorry" not in summary.lower()
