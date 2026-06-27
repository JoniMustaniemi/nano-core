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
NOTE_REQUEST_PATTERNS: tuple[str, ...] = (
    r"\badd\s+(?:a\s+)?note\b",
    r"\bsave\s+(?:a\s+)?note\b",
    r"\bwrite\s+(?:this\s+)?down\b",
    r"\bremember\s+(?:this|that)?\b",
)
NOTE_LIST_PATTERNS: tuple[str, ...] = (
    r"\b(?:list|show|read|what(?:'s| is)?)\s+(?:my\s+)?notes\b",
    r"\bwhat\s+(?:do\s+you\s+)?remember\b",
    r"\bwhat\s+have\s+you\s+(?:remembered|saved)\b",
)
NOTE_LOOKUP_PATTERNS: tuple[str, ...] = (
    r"\bwhat(?:'s| is| was| were)\s+(?:my|the)\b",
    r"\bwhat\s+did\s+i\s+(?:save|write|note|remember)\b",
    r"\bwhat\s+was\s+(?:the\s+)?\w+",
    r"\bdo\s+you\s+remember\b",
    r"\bfind\s+(?:my\s+)?note\b",
    r"\bsearch\s+(?:my\s+)?notes\b",
)
NOTE_LOOKUP_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "about",
        "an",
        "and",
        "did",
        "do",
        "for",
        "hey",
        "hi",
        "i",
        "is",
        "it",
        "me",
        "my",
        "nano",
        "of",
        "on",
        "please",
        "remember",
        "saved",
        "the",
        "to",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "you",
    }
)


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


def should_answer_without_tools(message: str) -> bool:
    """
    Return whether answer without tools.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    lowered = message.lower()
    return any(trigger in lowered for trigger in DIRECT_ANSWER_TRIGGERS)


def is_health_check_request(message: str) -> bool:
    """
    Return whether health check request.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    lowered = " ".join(message.lower().split())
    explicit_patterns = (
        r"\bcheck\s+(?:your|my)\s+health\b",
        r"\bhealth\s+check\b",
        r"\brun\s+(?:a\s+)?(?:health\s+)?diagnostics?\b",
        r"\bdiagnostics?\s+check\b",
        r"\bcheck\s+diagnostics?\b",
        r"\bcheck\s+yourself\b",
        r"\bself\s+check\b",
        r"\bsystem\s+check\b",
    )
    return any(re.search(pattern, lowered) for pattern in explicit_patterns)


def is_note_add_request(message: str) -> bool:
    """
    Return whether note add request.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    lowered = " ".join(message.lower().split())
    return any(re.search(pattern, lowered) for pattern in NOTE_REQUEST_PATTERNS)


def is_note_list_request(message: str) -> bool:
    """
    Return whether note list request.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    lowered = " ".join(message.lower().split())
    return any(re.search(pattern, lowered) for pattern in NOTE_LIST_PATTERNS)


def is_note_lookup_request(message: str) -> bool:
    """
    Return whether note lookup request.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    lowered = " ".join(message.lower().split())
    return any(re.search(pattern, lowered) for pattern in NOTE_LOOKUP_PATTERNS)


def note_content_from_message(message: str) -> str | None:
    """
    Extract note content from a note request.

    Args:
        message: User message or prompt text.

    Returns:
        Note content when provided; otherwise None.
    """
    stripped = " ".join(message.strip().split())
    if not stripped:
        return None

    patterns = (
        r"(?i)^add\s+(?:a\s+)?note(?:\s+(?:that|saying|to\s+say|:))?\s+(?P<content>.+)$",
        r"(?i)^save\s+(?:a\s+)?note(?:\s+(?:that|saying|to\s+say|:))?\s+(?P<content>.+)$",
        r"(?i)^write\s+(?:this\s+)?down(?:\s*:)?\s+(?P<content>.+)$",
        r"(?i)^remember(?:\s+(?:this|that))?(?:\s*:)?\s+(?P<content>.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, stripped)
        if not match:
            continue
        content = match.group("content").strip()
        return content or None
    return None


def note_keywords_from_message(message: str) -> list[str]:
    """
    Extract keywords to search notes.

    Args:
        message: User message or prompt text.

    Returns:
        Keywords from the request.
    """
    words = re.findall(r"[a-z0-9]+", message.lower())
    keywords: list[str] = []
    for word in words:
        if len(word) < 3 or word in NOTE_LOOKUP_STOPWORDS:
            continue
        if word not in keywords:
            keywords.append(word)
    return keywords


def needs_wipe_confirmation(message: str) -> bool:
    """
    Return whether wipe confirmation.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    lowered = message.lower()
    return any(trigger in lowered for trigger in WIPE_REQUEST_TRIGGERS) and any(
        trigger in lowered for trigger in WIPE_TARGET_TRIGGERS
    )


def is_confirmation_message(message: str) -> bool:
    """
    Return whether confirmation message.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    lowered = message.strip().lower()
    return lowered in {"yes", "yes.", "confirm", "confirm.", "do it", "proceed"}


def is_rejection_message(message: str) -> bool:
    """
    Return whether rejection message.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    lowered = " ".join(message.strip().lower().strip(" .!?").split())
    return lowered in {
        "no",
        "cancel",
        "stop",
        "nothing",
        "never mind",
        "nevermind",
        "forget it",
    }


def wipe_confirmation_prompt(message: str) -> str:
    """
    Wipe confirmation prompt.

    Args:
        message: User message or prompt text.

    Returns:
        Generated or formatted string value.
    """
    subject = normalize_wipe_request(message)
    return (
        f'You are asking me to do this: "{subject}". '
        "If this is truly your intention, reply yes to proceed or no to cancel."
    )


def normalize_wipe_request(message: str) -> str:
    """
    Normalize wipe request.

    Args:
        message: User message or prompt text.

    Returns:
        Generated or formatted string value.
    """
    normalized = " ".join(message.strip().split())
    if not normalized:
        return "wipe what I am keeping"
    return normalized[:160]


def is_wipe_confirmation_prompt(message: str) -> bool:
    """
    Return whether wipe confirmation prompt.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    lowered = message.lower()
    return "reply yes to proceed or no to cancel" in lowered


def tool_matches_request(message: str, tool_name: str) -> bool:
    """
    Build tool metadata for matches request.

    Args:
        message: User message or prompt text.
        tool_name: Registered tool name.

    Returns:
        True when the condition is met; otherwise false.
    """
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
    if tool_name == "check_health":
        return is_health_check_request(message)
    if tool_name == "add_note":
        return is_note_add_request(message)
    if tool_name == "list_notes":
        return is_note_list_request(message)
    return any(keyword in lowered for keyword in rule.keywords)


def needs_timer_duration(message: str) -> bool:
    """
    Return whether timer duration.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    lowered = message.lower()
    if _has_timer_cancel_keyword(lowered):
        return False
    if not any(trigger in lowered for trigger in TIMER_REQUEST_TRIGGERS):
        return False
    if not any(keyword in lowered for keyword in TIMER_START_KEYWORDS):
        return False
    return extract_duration_args(lowered) is None


def duration_args_from_message(message: str) -> dict[str, Any] | None:
    """
    Handle duration args from message.

    Args:
        message: User message or prompt text.

    Returns:
        Dictionary containing the requested data.
    """
    return extract_duration_args(message)


def is_timer_start_request(message: str) -> bool:
    """
    Return whether timer start request.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    lowered = message.lower()
    if _has_timer_cancel_keyword(lowered):
        return False
    return any(trigger in lowered for trigger in TIMER_REQUEST_TRIGGERS) and any(
        keyword in lowered for keyword in TIMER_START_KEYWORDS
    )


def is_timer_cancel_request(message: str) -> bool:
    """
    Return whether timer cancel request.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    lowered = message.lower()
    has_timer_trigger = any(trigger in lowered for trigger in TIMER_REQUEST_TRIGGERS)
    return has_timer_trigger and _has_timer_cancel_keyword(lowered)


def is_timer_status_request(message: str) -> bool:
    """
    Return whether timer status request.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
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
    """
    Handle has timer cancel keyword.

    Args:
        lowered_message: Lowered message value.

    Returns:
        True when the condition is met; otherwise false.
    """
    return any(keyword in lowered_message for keyword in TIMER_CANCEL_KEYWORDS)


def timer_confirmation(args: dict[str, Any]) -> str:
    """
    Build timer text for confirmation.

    Args:
        args: Tool argument dictionary.

    Returns:
        Generated or formatted string value.
    """
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
    """
    Build tool metadata for signature.

    Args:
        tool_name: Registered tool name.
        args: Tool argument dictionary.

    Returns:
        Generated or formatted string value.
    """
    return f"{tool_name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"


def parse_decision(raw: str) -> Decision:
    """
    Parse decision.

    Args:
        raw: Raw input value to parse.

    Returns:
        Decision result.
    """
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
    """
    Extract json.

    Args:
        raw: Raw input value to parse.

    Returns:
        Any result.
    """
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
