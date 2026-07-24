import json

from app.assistant.response_composer import ResponseComposer
from app.assistant.response_source import (
    confirmation_source,
    follow_up_source,
    tool_error_source,
    tool_result_source,
)


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


def test_compose_confirmation_uses_follow_up_text() -> None:
    composer = ResponseComposer()
    source = follow_up_source(
        user_message="Start a timer.",
        facts="How long should the timer run? Try 30 seconds or 5 minutes.",
        conversation_id="default",
    )

    content = composer.compose(_StubClient(), source)

    assert content == "How long should the timer run? Try 30 seconds or 5 minutes."


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


def test_compose_improvement_plan_success_strips_meta_goal_phrasing() -> None:
    composer = ResponseComposer()
    payload = json.dumps(
        {
            "ok": True,
            "title": "Draft an improvement plan for clearer timer messages.",
            "goal": "Draft an improvement plan for clearer timer messages.",
        }
    )
    source = tool_result_source(
        user_message="Draft an improvement plan for clearer timer messages.",
        facts=payload,
        tool_name="draft_improvement_plan",
        conversation_id="default",
    )

    content = composer.compose(_StubClient(), source)

    assert content == (
        "I finished a new improvement plan about clearer timer messages. "
        "Open the Plans tab to read it."
    )


def test_compose_improvement_plan_success_points_to_plans_tab() -> None:
    composer = ResponseComposer()
    payload = json.dumps(
        {
            "ok": True,
            "title": "Clearer timer messages",
            "goal": "clearer timer messages",
        }
    )
    source = tool_result_source(
        user_message="Improve yourself.",
        facts=payload,
        tool_name="draft_improvement_plan",
        conversation_id="default",
    )

    content = composer.compose(_StubClient(), source)

    assert content == (
        "I finished a new improvement plan about Clearer timer messages. "
        "Open the Plans tab to read it."
    )


def test_compose_improvement_plan_success_truncates_long_theme() -> None:
    composer = ResponseComposer()
    long_title = (
        "Improve timer copy so every failure path explains what went wrong and what to do next"
    )
    payload = json.dumps({"ok": True, "title": long_title, "goal": long_title})
    source = tool_result_source(
        user_message="Improve yourself.",
        facts=payload,
        tool_name="draft_improvement_plan",
        conversation_id="default",
    )

    content = composer.compose(_StubClient(), source)

    assert "Improve timer copy so every failure path explains what we..." in content
    assert "Open the Plans tab to read it." in content


def test_compose_improvement_plan_gate_is_first_person() -> None:
    composer = ResponseComposer()
    payload = json.dumps(
        {
            "ok": False,
            "step": "gate",
            "error": "A plan is already waiting for review.",
            "goal": "clearer timer messages",
        }
    )
    source = tool_result_source(
        user_message="Improve yourself.",
        facts=payload,
        tool_name="draft_improvement_plan",
        conversation_id="default",
    )

    content = composer.compose(_StubClient(), source)

    assert "Plans tab" in content
    assert "mark it processed" in content


def test_compose_improvement_plan_tool_error_uses_failure_copy() -> None:
    composer = ResponseComposer()
    payload = json.dumps(
        {
            "ok": False,
            "step": "draft",
            "error": "Could not draft an improvement plan.",
        }
    )
    source = tool_error_source(
        user_message="Improve yourself.",
        facts=payload,
        tool_name="draft_improvement_plan",
        conversation_id="default",
    )

    content = composer.compose(_StubClient(), source)

    assert content.startswith("I could not draft an improvement plan.")
    assert "drafting the plan" in content
