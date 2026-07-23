from __future__ import annotations

from datetime import datetime
from typing import Any

from app.memory import repository
from app.tools.base import ToolSpec
from app.tools.errors import ToolError
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
    due_at_raw = str(args.get("due_at", "")).strip()
    if not due_at_raw:
        raise ToolError("Reminder due_at is required in ISO-8601 format.")
    try:
        due_at = datetime.fromisoformat(due_at_raw)
    except ValueError as exc:
        raise ToolError(f"Invalid reminder due_at: {due_at_raw}") from exc
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
        announcement="Scheduling a reminder.",
        keywords=("reminder", "remind me"),
    )
)

register_tool(
    ToolSpec(
        name="list_reminders",
        description="list reminders.",
        args_schema={},
        handler=_list_reminders,
        announcement="Checking reminders.",
        keywords=("reminders", "reminder"),
        ui_label="List reminders",
        ui_message="List reminders.",
        ui_category="Reminders",
        ui_description="Show scheduled reminders.",
    )
)
