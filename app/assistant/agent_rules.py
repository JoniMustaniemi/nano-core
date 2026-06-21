from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.assistant.agent_types import Decision
from app.duration import extract_duration_args


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
        keywords=("health", "status", "diagnostic", "check yourself", "self check"),
    ),
}

DIRECT_ANSWER_TRIGGERS: tuple[str, ...] = (
    "what can you do",
    "what do you do",
    "what are your capabilities",
    "capabilities",
    "who are you",
    "introduce yourself",
    "what are you",
    "help",
)

WIPE_REQUEST_TRIGGERS: tuple[str, ...] = (
    "wipe",
    "erase",
    "clear",
    "reset",
    "delete",
    "remove",
    "purge",
    "forget",
)

WIPE_TARGET_TRIGGERS: tuple[str, ...] = (
    "database",
    "memory",
    "data",
    "local",
    "stored",
    "everything",
    "yourself",
    "your self",
)

TIMER_REQUEST_TRIGGERS: tuple[str, ...] = (
    "timer",
    "countdown",
)
TIMER_START_KEYWORDS: tuple[str, ...] = (
    "start",
    "set",
    "create",
    "begin",
)
TIMER_CANCEL_KEYWORDS: tuple[str, ...] = (
    "cancel",
    "stop",
    "delete",
    "remove",
    "clear",
    "end",
    "kill",
)

def tool_announcement(tool_name: str) -> str:
    rule = TOOL_RULES.get(tool_name)
    if rule is None:
        return "Performing a local action."
    return rule.announcement


def should_answer_without_tools(message: str) -> bool:
    lowered = message.lower()
    return any(trigger in lowered for trigger in DIRECT_ANSWER_TRIGGERS)


def is_health_check_request(message: str) -> bool:
    lowered = message.lower()
    triggers = ("health", "status", "diagnostic", "check yourself", "self check")
    return any(trigger in lowered for trigger in triggers)


def needs_wipe_confirmation(message: str) -> bool:
    lowered = message.lower()
    return any(trigger in lowered for trigger in WIPE_REQUEST_TRIGGERS) and any(
        trigger in lowered for trigger in WIPE_TARGET_TRIGGERS
    )


def is_confirmation_message(message: str) -> bool:
    lowered = message.strip().lower()
    return lowered in {"yes", "yes.", "confirm", "confirm.", "do it", "proceed"}


def is_rejection_message(message: str) -> bool:
    lowered = message.strip().lower()
    return lowered in {"no", "no.", "cancel", "cancel.", "stop", "never mind", "nevermind"}


def wipe_confirmation_prompt(message: str) -> str:
    subject = normalize_wipe_request(message)
    return (
        f"You are asking me to do this: \"{subject}\". "
        "If this is truly your intention, reply yes to proceed or no to cancel."
    )


def normalize_wipe_request(message: str) -> str:
    normalized = " ".join(message.strip().split())
    if not normalized:
        return "wipe what I am keeping"
    return normalized[:160]


def is_wipe_confirmation_prompt(message: str) -> bool:
    lowered = message.lower()
    return "reply yes to proceed or no to cancel" in lowered


def tool_matches_request(message: str, tool_name: str) -> bool:
    lowered = message.lower()
    rule = TOOL_RULES.get(tool_name)
    if rule is None:
        return True
    if tool_name == "run_python" and re.search(r"\d+\s*[\+\-\*/]\s*\d+", lowered):
        return True
    if tool_name == "start_timer":
        return is_timer_start_request(message)
    if tool_name == "list_timers":
        return is_timer_status_request(message)
    if tool_name == "cancel_timers":
        return is_timer_cancel_request(message)
    return any(keyword in lowered for keyword in rule.keywords)


def needs_timer_duration(message: str) -> bool:
    lowered = message.lower()
    if _has_timer_cancel_keyword(lowered):
        return False
    if not any(trigger in lowered for trigger in TIMER_REQUEST_TRIGGERS):
        return False
    if not any(keyword in lowered for keyword in TIMER_START_KEYWORDS):
        return False
    return extract_duration_args(lowered) is None


def duration_args_from_message(message: str) -> dict[str, Any] | None:
    return extract_duration_args(message)


def is_timer_start_request(message: str) -> bool:
    lowered = message.lower()
    if _has_timer_cancel_keyword(lowered):
        return False
    return any(trigger in lowered for trigger in TIMER_REQUEST_TRIGGERS) and any(
        keyword in lowered for keyword in TIMER_START_KEYWORDS
    )


def is_timer_cancel_request(message: str) -> bool:
    lowered = message.lower()
    has_timer_trigger = any(trigger in lowered for trigger in TIMER_REQUEST_TRIGGERS)
    return has_timer_trigger and _has_timer_cancel_keyword(lowered)


def is_timer_status_request(message: str) -> bool:
    lowered = message.lower()
    if _has_timer_cancel_keyword(lowered):
        return False
    if not any(trigger in lowered for trigger in TIMER_REQUEST_TRIGGERS):
        return False
    status_keywords = (
        "active",
        "running",
        "left",
        "remaining",
        "status",
        "list",
        "check",
        "how long",
        "what timers",
    )
    return any(keyword in lowered for keyword in status_keywords)


def _has_timer_cancel_keyword(lowered_message: str) -> bool:
    return any(keyword in lowered_message for keyword in TIMER_CANCEL_KEYWORDS)


def timer_confirmation(args: dict[str, Any]) -> str:
    if "duration_hours" in args:
        amount = int(args["duration_hours"])
        unit = "hour" if amount == 1 else "hours"
        return f"The timer is set for {amount} {unit}."

    if "duration_seconds" in args:
        amount = int(args["duration_seconds"])
        unit = "second" if amount == 1 else "seconds"
        return f"The timer is set for {amount} {unit}."

    amount = int(args["duration_minutes"])
    unit = "minute" if amount == 1 else "minutes"
    return f"The timer is set for {amount} {unit}."


def tool_signature(tool_name: str, args: dict[str, Any]) -> str:
    return f"{tool_name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"


def parse_decision(raw: str) -> Decision:
    payload = extract_json(raw)
    if isinstance(payload, dict):
        decision_type = payload.get("type")
        if decision_type == "final" and isinstance(payload.get("content"), str):
            return {"type": "final", "content": payload["content"]}
        if decision_type == "tool_call":
            tool = payload.get("tool")
            args = payload.get("args", {})
            if isinstance(tool, str) and isinstance(args, dict):
                return {"type": "tool_call", "tool": tool, "args": args}
    return {"type": "invalid"}


def extract_json(raw: str) -> Any:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
