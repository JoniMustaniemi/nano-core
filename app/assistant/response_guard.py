from __future__ import annotations

import re
from typing import Any, cast

from app.assistant.prompts import (
    ACTUAL_ANSWER_REWRITE_SYSTEM_PROMPT,
    THIRD_PERSON_REWRITE_SYSTEM_PROMPT,
    UNSUPPORTED_CONTINUATION_REWRITE_SYSTEM_PROMPT,
)

_THIRD_PERSON_SELF_PATTERNS = (
    re.compile(
        r"\bnano\s+(?:is|was|has|had|will|would|can|could|should|"
        r"reports|reported|says|said|states|stated|indicates|indicated|"
        r"ran|runs|checked|finished|answered|needs|called|used)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bnano's\b", re.IGNORECASE),
    re.compile(r"\bby nano\b", re.IGNORECASE),
    re.compile(r"(^|[,.!?]\s+)\bnano\b(?=[,.!?]|$)", re.IGNORECASE),
)

_SELF_DESCRIPTION_PATTERNS = (
    re.compile(r"\bi\s+apologize\b", re.IGNORECASE),
    re.compile(r"\bi(?:'m| am)\s+sorry\b", re.IGNORECASE),
    re.compile(r"\bi(?:'m| am)\s+nano\b", re.IGNORECASE),
    re.compile(r"\bi\s+do\s+not\s+have\s+the\s+ability\b", re.IGNORECASE),
    re.compile(r"\bi\s+don't\s+have\s+the\s+ability\b", re.IGNORECASE),
    re.compile(r"\bi\s+do\s+not\s+have\s+access\s+to\b", re.IGNORECASE),
    re.compile(r"\bi\s+don't\s+have\s+access\s+to\b", re.IGNORECASE),
    re.compile(r"\bi(?:'m| am)\s+programmed\s+to\b", re.IGNORECASE),
    re.compile(r"\bbased on the information i(?:'ve| have) been trained on\b", re.IGNORECASE),
    re.compile(r"\bexternal databases\b", re.IGNORECASE),
    re.compile(r"\breal[- ]time information\b", re.IGNORECASE),
    re.compile(r"\bi(?:'d| would)\s+be happy to help\b", re.IGNORECASE),
    re.compile(r"\blocal[- ]first personal assistant\b", re.IGNORECASE),
    re.compile(r"\bprivate local assistant\b", re.IGNORECASE),
    re.compile(r"\bi can execute local python code\b", re.IGNORECASE),
    re.compile(r"\bi can answer questions\b", re.IGNORECASE),
    re.compile(r"\buse local tools\b", re.IGNORECASE),
    re.compile(r"\bread and write text files\b", re.IGNORECASE),
)

_IDENTITY_OR_CAPABILITY_TRIGGERS = (
    "what can you do",
    "what do you do",
    "what are your capabilities",
    "what are you able to do",
    "capabilities",
    "who are you",
    "what are you",
    "introduce yourself",
)

_UNSUPPORTED_CONTINUATION_PATTERNS = (
    re.compile(r"\bi\s+will\s+continue\s+to\b", re.IGNORECASE),
    re.compile(
        r"\bi(?:'ll| will)\s+keep\s+(?:checking|monitoring|running|working)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bi(?:'ll| will)\s+provide\s+(?:you\s+with\s+)?(?:the\s+)?results\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bi(?:'m| am)\s+currently\s+running\s+diagnostics\b", re.IGNORECASE),
    re.compile(r"\bdiagnostics\s+are\s+(?:still\s+)?running\b", re.IGNORECASE),
    re.compile(r"\bas\s+they\s+are\s+determined\b", re.IGNORECASE),
    re.compile(
        r"\bas\s+soon\s+as\s+(?:they|it)\s+(?:are|is)\s+"
        r"(?:available|ready|determined)\b",
        re.IGNORECASE,
    ),
)

def talks_about_nano_in_third_person(content: str) -> bool:
    """
    Return whether a user-facing answer describes Nano from the outside.

    Args:
        content: Text content to inspect.

    Returns:
        True when the answer appears to use third-person self-reference.
    """
    return any(pattern.search(content) for pattern in _THIRD_PERSON_SELF_PATTERNS)


def enforce_first_person_self_reference(client: Any, content: str) -> str:
    """
    Rewrite model output once if it talks about Nano in third person.

    Args:
        client: LLM client used to revise responses.
        content: User-facing response content.

    Returns:
        Original content, or a first-person rewrite when needed.
    """
    if not content.strip() or not talks_about_nano_in_third_person(content):
        return content

    messages = [
        {
            "role": "system",
            "content": THIRD_PERSON_REWRITE_SYSTEM_PROMPT,
        },
        {"role": "user", "content": content},
    ]
    revised = cast(str, client.complete(messages=messages)).strip()
    return revised or content


def looks_like_self_description_instead_of_answer(user_message: str, content: str) -> bool:
    """
    Return whether the answer describes Nano instead of answering the user.

    Args:
        user_message: User message or prompt text.
        content: Text content to inspect.

    Returns:
        True when the response appears to be an accidental identity/capability fallback.
    """
    lowered_message = user_message.lower()
    if any(trigger in lowered_message for trigger in _IDENTITY_OR_CAPABILITY_TRIGGERS):
        return False
    return any(pattern.search(content) for pattern in _SELF_DESCRIPTION_PATTERNS)


def enforce_actual_answer(client: Any, user_message: str, content: str) -> str:
    """
    Rewrite model output once if it dodges the question by describing Nano.

    Args:
        client: LLM client used to revise responses.
        user_message: User message or prompt text.
        content: User-facing response content.

    Returns:
        Original content, or a revised answer when the model echoed its identity.
    """
    if not content.strip() or not looks_like_self_description_instead_of_answer(
        user_message,
        content,
    ):
        return content

    messages = [
        {
            "role": "system",
            "content": ACTUAL_ANSWER_REWRITE_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": (
                f"User question: {user_message}\n\n"
                f"Previous wrong answer:\n{content}"
            ),
        },
    ]
    revised = cast(str, client.complete(messages=messages)).strip()
    return revised or content


def implies_unsupported_continuation(content: str) -> bool:
    """
    Return whether the answer implies Nano will continue work after responding.

    Args:
        content: Text content to inspect.

    Returns:
        True when the response implies unsupported future/background processing.
    """
    return any(pattern.search(content) for pattern in _UNSUPPORTED_CONTINUATION_PATTERNS)


def enforce_no_unsupported_continuation(
    client: Any,
    user_message: str,
    content: str,
) -> str:
    """
    Rewrite model output once if it promises unsupported continued work.

    Args:
        client: LLM client used to revise responses.
        user_message: User message or prompt text.
        content: User-facing response content.

    Returns:
        Original content, or a revised answer without unsupported future promises.
    """
    if not content.strip() or not implies_unsupported_continuation(content):
        return content

    messages = [
        {
            "role": "system",
            "content": UNSUPPORTED_CONTINUATION_REWRITE_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": (
                f"User request: {user_message}\n\n"
                f"Previous wrong answer:\n{content}"
            ),
        },
    ]
    revised = cast(str, client.complete(messages=messages)).strip()
    return revised or content


def enforce_user_facing_answer(client: Any, user_message: str, content: str) -> str:
    """
    Apply answer-quality guards to model output intended for the user.

    Args:
        client: LLM client used to revise responses.
        user_message: User message or prompt text.
        content: User-facing response content.

    Returns:
        Guarded response content.
    """
    content = enforce_actual_answer(client, user_message, content)
    content = enforce_no_unsupported_continuation(client, user_message, content)
    return enforce_first_person_self_reference(client, content)
