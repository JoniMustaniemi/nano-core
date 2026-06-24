from __future__ import annotations

from datetime import datetime
from typing import Any

from app.memory import repository
from app.tools.base import ToolSpec
from app.tools.registry import register_tool


def _add_reminder(args: dict[str, Any]) -> str:
    """
    Add reminder.

    Args:
        args: Tool argument dictionary.

    Returns:
        Generated or formatted string value.
    """
    content = str(args.get("content", ""))
    due_at = datetime.fromisoformat(str(args.get("due_at", "")))
    reminder = repository.add_reminder(content, due_at)
    return f"saved reminder {reminder.id}: {reminder.content}"


def _list_reminders(args: dict[str, Any]) -> str:
    """
    List reminders.

    Args:
        args: Tool argument dictionary.

    Returns:
        Generated or formatted string value.
    """
    del args
    reminders = repository.list_reminders()
    return (
        "\n".join(
            f"{reminder.id}: {reminder.content} @ {reminder.due_at.isoformat()}"
            for reminder in reminders
        )
        or "No reminders."
    )


register_tool(
    ToolSpec(
        name="add_reminder",
        description="save a reminder.",
        args_schema={
            "content": "Reminder text.",
            "due_at": "Reminder time in ISO-8601 format.",
        },
        handler=_add_reminder,
    )
)

register_tool(
    ToolSpec(
        name="list_reminders",
        description="list reminders.",
        args_schema={},
        handler=_list_reminders,
    )
)
