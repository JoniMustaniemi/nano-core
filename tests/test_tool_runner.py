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
