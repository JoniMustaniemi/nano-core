import json
from types import SimpleNamespace

from app.assistant.tool_runner import ToolRunner


def _silence_voice(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.assistant.tool_runner.GladosVoiceService.announce",
        lambda self, text: None,
    )


def test_tool_runner_announces_and_sets_working_before_handler(monkeypatch) -> None:
    working: list[dict[str, str]] = []
    announced: list[str] = []
    monkeypatch.setattr(
        "app.assistant.tool_runner.activity.working",
        lambda **kwargs: working.append(kwargs),
    )
    monkeypatch.setattr(
        "app.assistant.tool_runner.GladosVoiceService.announce",
        lambda self, text: announced.append(text),
    )
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


def test_tool_runner_can_skip_announcement(monkeypatch) -> None:
    announced: list[str] = []
    monkeypatch.setattr(
        "app.assistant.tool_runner.activity.working",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "app.assistant.tool_runner.GladosVoiceService.announce",
        lambda self, text: announced.append(text),
    )
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


def test_tool_runner_unknown_tool_returns_error_result(monkeypatch) -> None:
    runner = ToolRunner()
    _silence_voice(monkeypatch)

    result = runner.execute("missing_tool_xyz", {})

    payload = json.loads(result.content)
    assert result.ok is False
    assert "Unknown tool" in payload["error"]


def test_tool_runner_wraps_tool_error(monkeypatch) -> None:
    from app.tools.errors import ToolError

    runner = ToolRunner()
    _silence_voice(monkeypatch)

    def _raise_tool_error(_args):
        raise ToolError("bad input")

    monkeypatch.setattr(
        "app.assistant.tool_runner.get_tool",
        lambda name: SimpleNamespace(name=name, handler=_raise_tool_error),
    )

    result = runner.execute("demo_tool", {})

    payload = json.loads(result.content)
    assert result.ok is False
    assert payload["error"] == "bad input"


def test_tool_runner_wraps_unexpected_exception(monkeypatch) -> None:
    runner = ToolRunner()
    _silence_voice(monkeypatch)

    def _raise_runtime(_args):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "app.assistant.tool_runner.get_tool",
        lambda name: SimpleNamespace(name=name, handler=_raise_runtime),
    )

    result = runner.execute("demo_tool", {})

    payload = json.loads(result.content)
    assert result.ok is False
    assert "boom" in payload["error"]


def test_tool_runner_treats_structured_ok_false_as_failure(monkeypatch) -> None:
    runner = ToolRunner()
    announced: list[str] = []
    reported: list[dict[str, str]] = []
    monkeypatch.setattr(
        "app.assistant.tool_runner.GladosVoiceService.announce",
        lambda self, text: announced.append(text),
    )
    monkeypatch.setattr(
        "app.assistant.tool_runner.activity.error",
        lambda **kwargs: reported.append(kwargs),
    )
    payload = json.dumps(
        {
            "ok": False,
            "step": "draft",
            "error": "Could not draft an improvement plan.",
            "goal": "clearer timer messages",
        }
    )
    monkeypatch.setattr(
        "app.assistant.tool_runner.get_tool",
        lambda name: SimpleNamespace(name=name, handler=lambda _args: payload),
    )

    result = runner.execute("draft_improvement_plan", {})

    assert result.ok is False
    assert announced == [
        "Drafting an improvement plan",
        "I could not draft the improvement plan.",
    ]
    assert reported
    assert reported[0]["title"] == "I could not draft an improvement plan."
