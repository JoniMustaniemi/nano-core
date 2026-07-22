from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolIntentRule:
    announcement: str
    keywords: tuple[str, ...] = ()


TOOL_RULES: dict[str, ToolIntentRule] = {
    "run_python": ToolIntentRule(
        announcement="Running a local procedure.",
        keywords=("python", "calculate", "compute", "run code"),
    ),
    "read_file": ToolIntentRule(
        announcement="Checking a file.",
        keywords=("file", "open", "read", "show"),
    ),
    "write_file": ToolIntentRule(
        announcement="Updating a file.",
        keywords=("write", "edit", "change", "update", "file"),
    ),
    "list_files": ToolIntentRule(
        announcement="Looking through local files.",
        keywords=("files", "folders", "directory", "workspace"),
    ),
    "add_note": ToolIntentRule(
        announcement="Saving that to memory.",
        keywords=("note", "remember", "write down", "save this"),
    ),
    "list_notes": ToolIntentRule(
        announcement="Checking memory.",
        keywords=("notes", "note", "remembered"),
    ),
    "add_reminder": ToolIntentRule(
        announcement="Scheduling a reminder.",
        keywords=("reminder", "remind me"),
    ),
    "list_reminders": ToolIntentRule(
        announcement="Checking reminders.",
        keywords=("reminders", "reminder"),
    ),
    "start_timer": ToolIntentRule(
        announcement="Starting a timer.",
        keywords=("timer", "countdown"),
    ),
    "list_timers": ToolIntentRule(
        announcement="Checking timers.",
        keywords=("timer", "timers"),
    ),
    "cancel_timers": ToolIntentRule(
        announcement="Cancelling timers.",
        keywords=("timer", "timers", "countdown"),
    ),
    "check_health": ToolIntentRule(
        announcement="Running a health diagnostic.",
        keywords=(
            "check your health",
            "health check",
            "run diagnostics",
            "run diagnostic",
            "diagnostic check",
            "diagnostics check",
            "check diagnostics",
            "check diagnostic",
            "check yourself",
            "self check",
            "system check",
        ),
    ),
    "create_pull_request": ToolIntentRule(
        announcement="Opening a pull request.",
        keywords=("pull request", "open pr", "create pr", "github pr"),
    ),
    "propose_self_changes": ToolIntentRule(
        announcement="Planning self-improvement changes.",
        keywords=("improve yourself", "fix yourself", "your code", "propose self"),
    ),
    "apply_updates_and_restart": ToolIntentRule(
        announcement="Pulling latest changes.",
        keywords=("pull latest", "download updates", "restart nano", "apply updates"),
    ),
}


def tool_announcement(tool_name: str) -> str:
    """
    Build tool metadata for announcement.

    Args:
        tool_name: Registered tool name.

    Returns:
        Generated or formatted string value.
    """
    rule = TOOL_RULES.get(tool_name)
    if rule is None:
        return "Performing a local action."
    return rule.announcement


def tool_signature(tool_name: str, args: dict[str, object]) -> str:
    """
    Build tool metadata for signature.

    Args:
        tool_name: Registered tool name.
        args: Tool argument dictionary.

    Returns:
        Generated or formatted string value.
    """
    import json

    return f"{tool_name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"
