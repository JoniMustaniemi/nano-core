import json

from app.assistant.response_guard import (
    collect_problems,
    detect_intent_mismatch,
    enforce_user_facing_answer,
    looks_like_refusal,
)
from app.assistant.response_source import confirmation_source


class _StubClient:
    def __init__(self, responses: list[str] | None = None) -> None:
        self.responses = list(responses or [])
        self.messages: list[list[dict[str, str]]] = []

    def complete(self, messages) -> str:
        self.messages.append(messages)
        if self.responses:
            return self.responses.pop(0)
        return '{"aligned": true, "problems": []}'


def test_wipe_confirmation_prompt_reflects_request_wording() -> None:
    from app.assistant.rules.messages import wipe_confirmation_prompt

    prompt = wipe_confirmation_prompt("Clear your memory.")
    assert "clear your memory" in prompt.lower()
    assert "say yes" in prompt.lower()
    assert "you are asking me to do this" not in prompt.lower()
    assert looks_like_refusal("I'm afraid I can't assist with that.")
    assert looks_like_refusal("I cannot assist with destructive requests.")
    assert not looks_like_refusal("You want me to erase what I remember.")


def test_detect_intent_mismatch_for_confirmation_refusal() -> None:
    source = confirmation_source(
        user_message="Wipe your database.",
        facts='User requested: "Wipe your database."',
    )
    content = "I'm afraid I can't assist with that. Reply yes to proceed or no to cancel."

    assert detect_intent_mismatch(source, content)


def test_collect_problems_skips_alignment_judge_when_regex_finds_issues() -> None:
    source = confirmation_source(
        user_message="Wipe your database.",
        facts='User requested: "Wipe your database."',
    )
    client = _StubClient()

    problems = collect_problems(
        client,
        source,
        "I'm afraid I can't assist with that. Reply yes to proceed or no to cancel.",
    )

    assert problems
    assert client.messages == []


def test_judge_alignment_fails_open_on_non_alignment_json() -> None:
    source = confirmation_source(
        user_message="Wipe your database.",
        facts='User requested: "Wipe your database."',
    )
    client = _StubClient(
        responses=['{"type":"final","content":"Unrelated planner payload."}']
    )

    problems = collect_problems(
        client,
        source,
        "You want me to erase what I remember. Reply yes to proceed or no to cancel.",
    )

    assert problems == []


def test_collect_problems_uses_alignment_judge_when_clean() -> None:
    source = confirmation_source(
        user_message="Wipe your database.",
        facts='User requested: "Wipe your database."',
    )
    client = _StubClient(
        responses=[
            json.dumps(
                {
                    "aligned": False,
                    "problems": ["Reply reports the wrong outcome."],
                }
            )
        ]
    )

    problems = collect_problems(
        client,
        source,
        "You want me to erase what I remember. Reply yes to proceed or no to cancel.",
    )

    assert problems == ["Reply reports the wrong outcome."]
    assert len(client.messages) == 1


def test_enforce_user_facing_answer_rewrites_confirmation_refusal() -> None:
    source = confirmation_source(
        user_message="Wipe your database.",
        facts='User requested: "Wipe your database."',
    )
    client = _StubClient(
        responses=[
            (
                "You want me to wipe your database. "
                "Say yes to proceed, or no to cancel."
            )
        ]
    )

    content = enforce_user_facing_answer(
        client,
        source,
        "I'm afraid I can't assist with that. Reply yes to proceed or no to cancel.",
    )

    assert "afraid" not in content.lower()
    assert "say yes" in content.lower()
    assert len(client.messages) == 2
    assert "Problems to fix" in client.messages[0][1]["content"]


def test_enforce_user_facing_answer_uses_confirmation_fallback_after_failed_rewrite() -> None:
    source = confirmation_source(
        user_message="Wipe your database.",
        facts='User requested: "Wipe your database."',
    )
    client = _StubClient(
        responses=[
            "I'm afraid I can't assist with that. Reply yes to proceed or no to cancel.",
            "I'm afraid I can't assist with that. Reply yes to proceed or no to cancel.",
        ]
    )

    content = enforce_user_facing_answer(
        client,
        source,
        "I'm afraid I can't assist with that. Reply yes to proceed or no to cancel.",
    )

    assert content.startswith("You want me to wipe your database.")
    assert "say yes" in content.lower()
    assert "afraid" not in content.lower()
