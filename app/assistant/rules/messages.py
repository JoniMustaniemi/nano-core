from __future__ import annotations

import re

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


def is_presence_confirmation(message: str) -> bool:
    lowered = " ".join(message.strip().lower().strip(" .!?").split())
    if is_confirmation_message(message):
        return True
    return lowered in {
        "yeah",
        "yep",
        "i'm here",
        "im here",
        "here",
        "present",
    }


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


_CONFIRMATION_CLOSERS: tuple[str, ...] = (
    "Say yes to proceed, or no to cancel.",
    "Reply yes if you want me to go ahead, or no to stop.",
    "If that's what you want, say yes; otherwise say no.",
)


def confirmation_followup(seed: str) -> str:
    """
    Return a varied yes/no confirmation instruction.

    Args:
        seed: Stable text used to pick a phrasing variant.

    Returns:
        Confirmation follow-up sentence.
    """
    if not seed:
        return _CONFIRMATION_CLOSERS[0]
    index = sum(ord(char) for char in seed) % len(_CONFIRMATION_CLOSERS)
    return _CONFIRMATION_CLOSERS[index]


def _confirmation_lead(subject: str) -> str:
    cleaned = subject.strip().rstrip(".!?")
    if not cleaned:
        return "You want me to wipe what I am keeping."
    lowered = cleaned.lower()
    if lowered.startswith(("wipe ", "erase ", "delete ", "clear ", "remove ")):
        return f"You want me to {lowered}."
    if lowered.startswith(("don't ", "do not ")):
        return f"You're asking me to {lowered}."
    return f"Just confirming - you want me to {lowered}."


def wipe_confirmation_prompt(message: str) -> str:
    """
    Wipe confirmation prompt.

    Args:
        message: User message or prompt text.

    Returns:
        Generated or formatted string value.
    """
    subject = normalize_wipe_request(message)
    return f"{_confirmation_lead(subject)} {confirmation_followup(subject)}"


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
    legacy_phrase = "reply yes to proceed or no to cancel"
    if legacy_phrase in lowered:
        return True
    return (
        "say yes" in lowered
        and "no" in lowered
        and any(marker in lowered for marker in ("proceed", "cancel", "go ahead", "stop"))
    )
