import json

from app.memory import repository
from app.tools import get_tool, list_tools, render_tool_prompt


def test_tool_registry_loads_builtin_tool_modules() -> None:
    tool_names = {tool.name for tool in list_tools()}

    assert "run_python" in tool_names
    assert "read_file" in tool_names
    assert "add_note" in tool_names
    assert "add_reminder" in tool_names
    assert "start_timer" in tool_names
    assert "check_health" in tool_names


def test_tool_prompt_lists_registered_tools() -> None:
    prompt = render_tool_prompt()

    assert "Available tools:" in prompt
    assert "- run_python(code, timeout_seconds):" in prompt
    assert '{"type":"tool_call","tool":"tool_name","args":{"key":"value"}}' in prompt


def test_get_tool_returns_registered_handler() -> None:
    tool = get_tool("list_notes")

    assert tool is not None
    assert tool.name == "list_notes"


def test_timer_tool_creates_timer_reminder() -> None:
    tool = get_tool("start_timer")

    assert tool is not None
    result = tool.handler({"duration_seconds": 30, "label": "Tea"})
    reminders = repository.list_reminders()

    assert "started timer" in result
    assert reminders[0].content == "[timer] Tea"


def test_health_tool_returns_structured_json(monkeypatch) -> None:
    tool = get_tool("check_health")

    assert tool is not None
    monkeypatch.setattr(
        "app.tools.health_tools.run_health_checks",
        lambda: [
            type(
                "Result",
                (),
                {"name": "database", "ok": True, "detail": "Database is reachable."},
            )(),
            type(
                "Result",
                (),
                {"name": "voice", "ok": False, "detail": "Voice backend is unavailable."},
            )(),
        ],
    )

    payload = json.loads(tool.handler({}))

    assert payload["overall"] == "error"
    assert payload["checks"][0]["name"] == "database"
    assert payload["checks"][1]["status"] == "error"
