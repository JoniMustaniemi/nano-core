from datetime import UTC, datetime, timedelta

import pytest

from app.memory import repository
from app.tools import get_tool
from app.tools.errors import ToolError


def test_add_reminder_saves_reminder() -> None:
    tool = get_tool("add_reminder")
    assert tool is not None

    due_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    result = tool.handler({"content": "Stretch", "due_at": due_at})
    reminders = repository.list_reminders()

    assert "saved reminder" in result
    assert reminders[0].content == "Stretch"


def test_add_reminder_rejects_invalid_due_at() -> None:
    tool = get_tool("add_reminder")
    assert tool is not None

    with pytest.raises(ToolError, match="Invalid reminder due_at"):
        tool.handler({"content": "Stretch", "due_at": "not-a-date"})


def test_add_reminder_requires_due_at() -> None:
    tool = get_tool("add_reminder")
    assert tool is not None

    with pytest.raises(ToolError, match="due_at is required"):
        tool.handler({"content": "Stretch", "due_at": ""})
