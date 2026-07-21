from __future__ import annotations

import re
from typing import Literal

from app.assistant.prompts import GUARD_REWRITE_SYSTEM_PROMPT
from app.llm.protocol import LLMClient

ViolationKind = Literal["self_description", "unsupported_continuation", "third_person"]

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

_VIOLATION_LABELS: dict[ViolationKind, str] = {
    "self_description": (
        "Described identity or capabilities instead of answering the user's question."
    ),
    "unsupported_continuation": (
        "Promised unsupported continued work after responding."
    ),
    "third_person": "Referred to Nano in third person instead of first person.",
}


def talks_about_nano_in_third_person(content: str) -> bool:
    """
    Return whether a user-facing answer describes Nano from the outside.

    Args:
        content: Text content to inspect.

    Returns:
        True when the answer appears to use third-person self-reference.
    """
    return any(pattern.search(content) for pattern in _THIRD_PERSON_SELF_PATTERNS)


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


def implies_unsupported_continuation(content: str) -> bool:
    """
    Return whether the answer implies Nano will continue work after responding.

    Args:
        content: Text content to inspect.

    Returns:
        True when the response implies unsupported future/background processing.
    """
    return any(pattern.search(content) for pattern in _UNSUPPORTED_CONTINUATION_PATTERNS)


def detect_violations(user_message: str, content: str) -> list[ViolationKind]:
    """
    Detect answer-quality violations in user-facing content.

    Args:
        user_message: Original user message.
        content: Candidate assistant reply.

    Returns:
        List of detected violation kinds.
    """
    violations: list[ViolationKind] = []
    if looks_like_self_description_instead_of_answer(user_message, content):
        violations.append("self_description")
    if implies_unsupported_continuation(content):
        violations.append("unsupported_continuation")
    if talks_about_nano_in_third_person(content):
        violations.append("third_person")
    return violations


def enforce_user_facing_answer(client: LLMClient, user_message: str, content: str) -> str:
    """
    Apply answer-quality guards to model output intended for the user.

    Args:
        client: LLM client used to revise responses.
        user_message: User message or prompt text.
        content: User-facing response content.

    Returns:
        Guarded response content.
    """
    if not content.strip():
        return content

    violations = detect_violations(user_message, content)
    if not violations:
        return content

    problem_lines = "\n".join(
        f"- {_VIOLATION_LABELS[violation]}" for violation in violations
    )
    messages = [
        {"role": "system", "content": GUARD_REWRITE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"User question: {user_message}\n\n"
                f"Previous wrong answer:\n{content}\n\n"
                f"Problems to fix:\n{problem_lines}"
            ),
        },
    ]
    revised = client.complete(messages=messages).strip()
    return revised or content
