from __future__ import annotations

import re

DIRECT_ANSWER_TRIGGERS: tuple[str, ...] = (
    "help",
)

CAPABILITY_QUESTION_TRIGGERS: tuple[str, ...] = (
    "what can you do",
    "what do you do",
    "what are your capabilities",
    "what are you able to do",
    "capabilities",
)

IDENTITY_QUESTION_TRIGGERS: tuple[str, ...] = (
    "who are you",
    "introduce yourself",
    "what are you",
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

INTERNAL_NOTE_LIST_PATTERNS: tuple[str, ...] = (
    r"\b(?:list|show|tell(?: me)?(?: about)?|read|what(?:'s| are)?)\b.*\binternal notes?\b",
    r"\binternal notes?\b.*\b(?:list|show|tell|read|what)\b",
    r"\bwhat\b.*\b(?:follow[\s-]?up|deferred)\b.*\bnotes?\b",
    r"\bwhat\b.*\bnotes?\b.*\b(?:follow[\s-]?up|discuss later|saved for later)\b",
    r"\bwhat do you want to discuss\b",
    r"\bwhat are you saving to discuss\b",
)

PULL_REQUEST_PATTERNS: tuple[str, ...] = (
    r"\b(?:create|open|make|start)\b.*\b(?:pull request|pr)\b",
    r"\b(?:pull request|pr)\b.*\b(?:create|open|make|start)\b",
    r"\b(?:need|want)\s+(?:a\s+)?(?:pull request|pr)\b",
    r"^\s*(?:pr|pull request)\s*$",
)

SELF_IMPROVE_PATTERNS: tuple[str, ...] = (
    r"\b(?:improve|fix|change|update|modify)\b.*\b(?:your(?:self)?|your code|nano)\b",
    r"\badd\b.*\b(?:to yourself|to nano)\b",
    r"\bpropose\s+self[\s-]?changes?\b",
)

SELF_IMPROVE_FOLLOW_UP_PATTERNS: tuple[str, ...] = (
    r"^\s*(?:do it|go ahead|proceed|yes do it)\s*\.?$",
)

VAGUE_SELF_IMPROVE_GOALS = frozenset({
    "",
    "general improvement",
    "improve yourself",
    "fix yourself",
    "update yourself",
    "modify yourself",
})


def is_vague_self_improve_goal(goal: str) -> bool:
    normalized = " ".join(goal.strip().split()).lower()
    return normalized in VAGUE_SELF_IMPROVE_GOALS


def _contains_term(lowered_message: str, term: str) -> bool:
    if " " in term:
        return term in lowered_message
    return re.search(rf"\b{re.escape(term)}\b", lowered_message) is not None


def is_pull_request_request(message: str) -> bool:
    """
    Return whether the message is a pull request creation request.

    Args:
        message: User message or prompt text.

    Returns:
        True when the message requests pull request creation.
    """
    lowered = " ".join(message.lower().split())
    return any(re.search(pattern, lowered) for pattern in PULL_REQUEST_PATTERNS)


def is_self_improve_request(message: str) -> bool:
    lowered = " ".join(message.lower().split())
    return any(re.search(pattern, lowered) for pattern in SELF_IMPROVE_PATTERNS)


def is_self_improve_follow_up(message: str) -> bool:
    lowered = " ".join(message.lower().split())
    return any(re.search(pattern, lowered) for pattern in SELF_IMPROVE_FOLLOW_UP_PATTERNS)


def extract_self_improve_goal(message: str) -> str:
    stripped = " ".join(message.strip().split())
    for prefix in (
        "improve yourself by ",
        "improve yourself to ",
        "improve yourself ",
        "fix yourself ",
        "update yourself ",
        "modify yourself ",
    ):
        if stripped.lower().startswith(prefix):
            return stripped[len(prefix) :].strip()
    return stripped


def is_identity_question(message: str) -> bool:
    """
    Return whether the message asks who Nano is.

    Args:
        message: User message or prompt text.

    Returns:
        True when the user is asking about Nano's identity.
    """
    lowered = message.lower()
    return any(trigger in lowered for trigger in IDENTITY_QUESTION_TRIGGERS)


def is_capability_question(message: str) -> bool:
    """
    Return whether the message asks what Nano can do.

    Args:
        message: User message or prompt text.

    Returns:
        True when the user is asking about capabilities.
    """
    lowered = message.lower()
    return any(trigger in lowered for trigger in CAPABILITY_QUESTION_TRIGGERS)


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


def is_internal_note_list_request(message: str) -> bool:
    """
    Return whether the user is asking about Nano's internal follow-up notes.

    Args:
        message: User message or prompt text.

    Returns:
        True when the message asks for internal notes.
    """
    lowered = " ".join(message.lower().split())
    return any(re.search(pattern, lowered) for pattern in INTERNAL_NOTE_LIST_PATTERNS)


def needs_wipe_confirmation(message: str) -> bool:
    """
    Return whether wipe confirmation.

    Args:
        message: User message or prompt text.

    Returns:
        True when the condition is met; otherwise false.
    """
    lowered = message.lower()
    return any(_contains_term(lowered, trigger) for trigger in WIPE_REQUEST_TRIGGERS) and any(
        _contains_term(lowered, trigger) for trigger in WIPE_TARGET_TRIGGERS
    )


def tool_matches_request(message: str, tool_name: str) -> bool:
    """
    Build tool metadata for matches request.

    Args:
        message: User message or prompt text.
        tool_name: Registered tool name.

    Returns:
        True when the condition is met; otherwise false.
    """
    from app.assistant.rules.timers import (
        is_timer_cancel_request,
        is_timer_start_request,
        is_timer_status_request,
    )
    from app.assistant.rules.tools import TOOL_RULES

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
    if tool_name == "create_pull_request":
        return is_pull_request_request(message)
    if tool_name == "propose_self_changes":
        return is_self_improve_request(message) or is_self_improve_follow_up(message)
    if tool_name == "add_note":
        return is_note_add_request(message)
    if tool_name == "list_notes":
        return is_note_list_request(message)
    if tool_name == "list_internal_notes":
        return is_internal_note_list_request(message)
    return any(keyword in lowered for keyword in rule.keywords)
