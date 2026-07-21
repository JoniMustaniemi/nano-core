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
