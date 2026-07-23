import json
from types import SimpleNamespace

from app.assistant.tool_runner import ToolRunner


def _silence_voice(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.assistant.tool_runner.GladosVoiceService.announce",
        lambda self, text: None,
    )


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
            "step": "plan",
            "error": "Could not parse change plan from the model for app/config.py.",
            "goal": "clearer timer messages",
        }
    )
    monkeypatch.setattr(
        "app.assistant.tool_runner.get_tool",
        lambda name: SimpleNamespace(name=name, handler=lambda _args: payload),
    )

    result = runner.execute("propose_self_changes", {})

    assert result.ok is False
    assert announced == ["I could not complete the self-improvement."]
    assert reported
    assert reported[0]["title"] == "I could not improve myself."
