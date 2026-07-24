from __future__ import annotations

import re
from collections import Counter

from app.assistant.prompts import POLISH_SYSTEM_PROMPT
from app.assistant.response_source import ResponseSource
from app.llm.protocol import LLMClient

_POLISH_PROMPT_MARKER = "polishing nano's final reply"


def should_polish(source: ResponseSource, content: str) -> bool:
    """
    Return whether a reply should receive a final polish pass.

    Args:
        source: Structured response input.
        content: Candidate assistant reply.

    Returns:
        True when polish is likely to improve the reply.
    """
    if not content.strip():
        return False
    if source.kind in {"follow_up", "confirmation"}:
        return False
    if source.kind == "answer":
        return True
    return looks_repetitive(content)


def looks_repetitive(content: str) -> bool:
    """
    Return whether text appears list-heavy or repetitive.

    Args:
        content: Candidate assistant reply.

    Returns:
        True when repetition heuristics match.
    """
    words = re.findall(r"[a-z']+", content.lower())
    if len(words) < 25:
        return False

    significant = [word for word in words if len(word) > 4]
    if any(count >= 3 for count in Counter(significant).values()):
        return True

    if content.count(",") >= 5:
        return True

    if re.search(r"\b(\w+)\b(?:.*\b\1\b){1,}", content, re.IGNORECASE):
        return True

    return False


def polish_user_facing_answer(
    client: LLMClient,
    source: ResponseSource,
    content: str,
) -> str:
    """
    Tighten a guarded reply before it is shown to the user.

    Args:
        client: LLM client used for polishing.
        source: Structured response input.
        content: Guarded response content.

    Returns:
        Polished response content.
    """
    if not should_polish(source, content):
        return content

    messages = [
        {"role": "system", "content": POLISH_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (f"User question: {source.user_message}\n\nDraft reply:\n{content}"),
        },
    ]
    polished = client.complete(messages=messages).strip()
    return polished or content


def is_polish_prompt(system_content: str) -> bool:
    """
    Return whether an LLM call is the response polish pass.

    Args:
        system_content: System prompt text.

    Returns:
        True when the call is a polish prompt.
    """
    return _POLISH_PROMPT_MARKER in system_content.lower()
