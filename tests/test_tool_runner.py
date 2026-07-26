import json
from types import SimpleNamespace

from helpers.voice_announce import patch_announce_voice, silence_announce_voice

from app.assistant.tool_runner import ToolRunner


def _silence_voice(monkeypatch) -> None:
    silence_announce_voice(monkeypatch)


def test_tool_runner_announces_and_sets_working_before_handler(monkeypatch) -> None:
    working: list[dict[str, str]] = []
    announced: list[str] = []
    monkeypatch.setattr(
        "app.assistant.tool_runner.activity.working",
        lambda **kwargs: working.append(kwargs),
    )
    patch_announce_voice(monkeypatch, announced)
    monkeypatch.setattr(
        "app.assistant.tool_runner.tool_announcement_for",
        lambda name: "Checking health.",
    )
    monkeypatch.setattr(
        "app.assistant.tool_runner.get_tool",
        lambda name: SimpleNamespace(
            name=name,
            handler=lambda _args: '{"ok": true}',
        ),
    )

    runner = ToolRunner()
    result = runner.execute("check_health", {})

    assert result.ok is True
    assert working == [
        {
            "title": "I'm running a health check.",
            "detail": "Give me a moment.",
            "source": "assistant.tool_runner",
        }
    ]
    assert announced == ["Checking health"]


def test_tool_runner_skips_pull_request_voice_announcement(monkeypatch) -> None:
    announced: list[str] = []
    monkeypatch.setattr(
        "app.assistant.tool_runner.activity.working",
        lambda **kwargs: None,
    )
    patch_announce_voice(monkeypatch, announced)
    monkeypatch.setattr(
        "app.assistant.tool_runner.get_tool",
        lambda name: SimpleNamespace(
            name=name,
            handler=lambda _args: '{"ok": true, "step": "complete"}',
            announcement="I'm opening a pull request.",
        ),
    )

    runner = ToolRunner()
    result = runner.execute("create_pull_request", {})

    assert result.ok is True
    assert announced == []


def test_tool_runner_can_skip_announcement(monkeypatch) -> None:
    announced: list[str] = []
    monkeypatch.setattr(
        "app.assistant.tool_runner.activity.working",
        lambda **kwargs: None,
    )
    patch_announce_voice(monkeypatch, announced)
    monkeypatch.setattr(
        "app.assistant.tool_runner.get_tool",
        lambda name: SimpleNamespace(
            name=name,
            handler=lambda _args: '{"ok": true}',
            announcement="Checking health.",
        ),
    )

    runner = ToolRunner()
    runner.execute("check_health", {}, announce=False)

    assert announced == []


def test_tool_runner_reports_structured_pull_request_failure(monkeypatch) -> None:
    errors: list[dict[str, str]] = []
    announced: list[str] = []
    monkeypatch.setattr(
        "app.assistant.tool_runner.activity.working",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "app.assistant.tool_runner.activity.error",
        lambda **kwargs: errors.append(kwargs),
    )
    patch_announce_voice(monkeypatch, announced)
    monkeypatch.setattr(
        "app.assistant.tool_runner.get_tool",
        lambda name: SimpleNamespace(
            name=name,
            handler=lambda _args: json.dumps(
                {"ok": False, "step": "lint", "error": "Lint checks failed."}
            ),
        ),
    )

    runner = ToolRunner()
    result = runner.execute("create_pull_request", {})

    assert result.ok is False
    assert errors == []
    assert announced == []


def test_tool_runner_reports_structured_draft_failure(monkeypatch) -> None:
    errors: list[dict[str, str]] = []
    announced: list[str] = []
    monkeypatch.setattr(
        "app.assistant.tool_runner.activity.working",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "app.assistant.tool_runner.activity.error",
        lambda **kwargs: errors.append(kwargs),
    )
    patch_announce_voice(monkeypatch, announced)
    monkeypatch.setattr(
        "app.assistant.tool_runner.get_tool",
        lambda name: SimpleNamespace(
            name=name,
            handler=lambda _args: json.dumps(
                {"ok": False, "step": "draft", "error": "Could not draft an improvement plan."}
            ),
        ),
    )

    runner = ToolRunner()
    result = runner.execute("draft_improvement_plan", {"goal": "clearer timer errors"})

    assert result.ok is False
    assert errors
    assert announced[-1] == "I could not draft the improvement plan."


def test_tool_runner_reports_generic_tool_error(monkeypatch) -> None:
    from app.tools.errors import ToolError

    errors: list[dict[str, str]] = []
    announced: list[str] = []
    monkeypatch.setattr(
        "app.assistant.tool_runner.activity.working",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "app.assistant.tool_runner.activity.error",
        lambda **kwargs: errors.append(kwargs),
    )
    patch_announce_voice(monkeypatch, announced)
    monkeypatch.setattr(
        "app.assistant.tool_runner.get_tool",
        lambda name: SimpleNamespace(
            name=name,
            handler=lambda _args: (_ for _ in ()).throw(ToolError("boom")),
        ),
    )

    runner = ToolRunner()
    result = runner.execute("check_health", {})

    assert result.ok is False
    assert errors
    assert announced[-1] == "I hit an error while trying to complete the task."
