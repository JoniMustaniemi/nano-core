from __future__ import annotations

import re

DIRECT_ANSWER_TRIGGERS: tuple[str, ...] = ("help",)

CAPABILITY_QUESTION_TRIGGERS: tuple[str, ...] = (
    "what can you do",
    "what do you do",
    "what are your capabilities",
    "what are you able to do",
    "capabilities",
)

IDENTITY_OR_CAPABILITY_TRIGGERS: tuple[str, ...] = CAPABILITY_QUESTION_TRIGGERS + (
    "who are you",
    "what are you",
    "introduce yourself",
)

IDENTITY_QUESTION_TRIGGERS: tuple[str, ...] = (
    "who are you",
    "introduce yourself",
    "what are you",
    "tell me about yourself",
    "tell me about himself",
    "tell me about herself",
    "tell me about itself",
    "tell me who you are",
    "who is nano",
    "what is nano",
)

IDENTITY_QUESTION_PATTERNS: tuple[str, ...] = (
    r"\bwho are you\b",
    r"\bintroduce yourself\b",
    r"\bwhat are you\b",
    r"\btell me about (?:yourself|himself|herself|itself)\b",
    r"\btell me who you are\b",
    r"\bwho is nano\b",
    r"\bwhat is nano\b",
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

INTERNAL_NOTE_LIST_PATTERNS: tuple[str, ...] = (
    r"\b(?:list|show|tell(?: me)?(?: about)?|read|what(?:'s| are)?)\b.*\binternal notes?\b",
    r"\binternal notes?\b.*\b(?:list|show|tell|read|what)\b",
    r"\bwhat\b.*\b(?:follow[\s-]?up|deferred)\b.*\bnotes?\b",
    r"\bwhat\b.*\bnotes?\b.*\b(?:follow[\s-]?up|discuss later|saved for later)\b",
    r"\bwhat do you want to discuss\b",
    r"\bwhat are you saving to discuss\b",
)

SYSTEM_ANALYSIS_PATTERNS: tuple[str, ...] = (
    r"\bsystem\s+analysis\b",
    r"\banalyze\s+(?:my\s+)?system\b",
    r"\brun\s+(?:a\s+)?system\s+analysis\b",
    r"\bcan\s+you\s+run\s+(?:a\s+)?system\s+analysis\b",
    r"\bcheck\s+(?:my\s+)?system\s+specs?\b",
    r"\bwhat\s+are\s+my\s+system\s+specs\b",
    r"\bhow\s+much\s+memory\b",
)

PULL_REQUEST_PATTERNS: tuple[str, ...] = (
    r"\b(?:create|open|make|start|begin|publish|submit|send|file|raise)\b.*\b(?:pull request|pool request|pr)\b",
    r"\b(?:pull request|pool request|pr)\b.*\b(?:create|open|make|start|begin|publish|submit|send|file|raise)\b",
    r"\b(?:need|want)\s+(?:a\s+|to\s+open\s+(?:a\s+)?)?(?:pull request|pool request|pr)\b",
    r"\b(?:can|could|may|would|let)\s+(?:you|me|us|i)\s+(?:open|create|make|start|submit|publish)\b.*\b(?:pull request|pool request|pr)\b",
    r"\b(?:i|we)\s+(?:need|want)\s+(?:a\s+|to\s+open\s+(?:a\s+)?)?(?:pull request|pool request|pr)\b",
    r"\bopen\s+up\s+(?:a\s+)?(?:pull request|pool request|pr)\b",
    r"^\s*(?:pr|pull request|pool request)\s*$",
)

REBOOT_REQUEST_PATTERNS: tuple[str, ...] = (
    r"\breboot\b.*\b(?:pi|raspberry|raspberry pi|device|system)\b",
    r"\b(?:pi|raspberry|raspberry pi)\b.*\breboot\b",
    r"\brestart\b.*\b(?:pi|raspberry|raspberry pi|device|system)\b",
    r"\b(?:pi|raspberry|raspberry pi)\b.*\brestart\b",
    r"^\s*reboot(?:\s+the\s+(?:pi|raspberry pi))?\s*\.?$",
)

SERVICE_RESTART_REQUEST_PATTERNS: tuple[str, ...] = (
    r"\brestart\b.*\b(?:yourself|nano|nano-?core|service|server)\b",
    r"\b(?:yourself|nano)\b.*\brestart\b",
    r"^\s*restart(?:\s+(?:yourself|nano|nano-core|the\s+service|the\s+server))?\s*\.?$",
)

_SERVICE_RESTART_EXCLUSIONS: tuple[str, ...] = (
    "pi",
    "raspberry",
    "device",
    "system",
)


def _normalize_pull_request_homophones(message: str) -> str:
    """Treat speech-recognition homophones like pool/pull as equivalent for PR intent."""
    normalized = re.sub(r"\bpool\s+request\b", "pull request", message)
    return re.sub(r"\bpool\s+pr\b", "pull pr", normalized)


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
    lowered = _normalize_pull_request_homophones(" ".join(message.lower().split()))
    return any(re.search(pattern, lowered) for pattern in PULL_REQUEST_PATTERNS)


def needs_reboot_confirmation(message: str) -> bool:
    lowered = " ".join(message.lower().split())
    return any(re.search(pattern, lowered) for pattern in REBOOT_REQUEST_PATTERNS)


def needs_service_restart_confirmation(message: str) -> bool:
    lowered = " ".join(message.lower().split())
    if any(term in lowered for term in _SERVICE_RESTART_EXCLUSIONS):
        return False
    return any(re.search(pattern, lowered) for pattern in SERVICE_RESTART_REQUEST_PATTERNS)


def is_identity_question(message: str) -> bool:
    """
    Return whether the message asks who Nano is.

    Args:
        message: User message or prompt text.

    Returns:
        True when the user is asking about Nano's identity.
    """
    lowered = " ".join(message.lower().split())
    if any(trigger in lowered for trigger in IDENTITY_QUESTION_TRIGGERS):
        return True
    return any(re.search(pattern, lowered) for pattern in IDENTITY_QUESTION_PATTERNS)


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


def is_system_analysis_request(message: str) -> bool:
    """
    Return whether the user wants Nano's system analysis report.

    Args:
        message: User message or prompt text.

    Returns:
        True when the message requests system analysis.
    """
    lowered = " ".join(message.lower().split())
    return any(re.search(pattern, lowered) for pattern in SYSTEM_ANALYSIS_PATTERNS)


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
        is_clear_all_timers_request,
        is_stopwatch_rename_request,
        is_stopwatch_start_request,
        is_stopwatch_stop_request,
        is_timer_cancel_request,
        is_timer_rename_request,
        is_timer_start_request,
        is_timer_status_request,
    )
    from app.assistant.rules.tools import get_tool_rule

    lowered = message.lower()
    rule = get_tool_rule(tool_name)
    if rule is None:
        return True
    if tool_name == "run_python" and re.search(r"\d+\s*[\+\-\*/]\s*\d+", lowered):
        return True
    if tool_name == "start_timer":
        return is_timer_start_request(message)
    if tool_name == "start_stopwatch":
        return is_stopwatch_start_request(message)
    if tool_name == "stop_stopwatches":
        return is_stopwatch_stop_request(message)
    if tool_name == "rename_timer":
        return is_timer_rename_request(message)
    if tool_name == "rename_stopwatch":
        return is_stopwatch_rename_request(message)
    if tool_name == "clear_all_timers":
        return is_clear_all_timers_request(message)
    if tool_name == "list_timers":
        return is_timer_status_request(message)
    if tool_name == "cancel_timers":
        return is_timer_cancel_request(message)
    if tool_name == "check_health":
        return is_health_check_request(message)
    if tool_name == "analyze_system":
        return is_system_analysis_request(message)
    if tool_name == "create_pull_request":
        return is_pull_request_request(message)
    if tool_name == "list_internal_notes":
        return is_internal_note_list_request(message)
    return any(keyword in lowered for keyword in rule.keywords)
