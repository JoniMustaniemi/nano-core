from __future__ import annotations

import re
from typing import Literal

from app.assistant.response_source import ResponseSource
from app.assistant.rules import IDENTITY_OR_CAPABILITY_TRIGGERS

ViolationKind = Literal[
    "self_description",
    "unsupported_continuation",
    "third_person",
    "intent_mismatch",
]

MAX_GUARD_PASSES = 2

_CONFIRMATION_SUFFIX = "reply yes to proceed or no to cancel"

_REFUSAL_PATTERNS = (
    re.compile(r"\bi(?:'m| am)\s+afraid\b", re.IGNORECASE),
    re.compile(r"\bi\s+can(?:'t| not)\s+assist\b", re.IGNORECASE),
    re.compile(r"\bi\s+cannot\s+assist\b", re.IGNORECASE),
    re.compile(r"\bi(?:'m| am)\s+unable\s+to\b", re.IGNORECASE),
    re.compile(r"\bi\s+can(?:'t| not)\s+help\b", re.IGNORECASE),
    re.compile(r"\bi\s+cannot\s+help\b", re.IGNORECASE),
    re.compile(r"\bnot\s+able\s+to\s+assist\b", re.IGNORECASE),
    re.compile(r"\bi\s+must\s+decline\b", re.IGNORECASE),
    re.compile(r"\bi\s+won(?:'t| will\s+not)\s+be\s+able\s+to\b", re.IGNORECASE),
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
    "unsupported_continuation": ("Promised unsupported continued work after responding."),
    "third_person": "Referred to yourself in third person instead of first person.",
    "intent_mismatch": ("Refused or contradicted the action you are performing or confirming."),
}


def looks_like_refusal(content: str) -> bool:
    return any(pattern.search(content) for pattern in _REFUSAL_PATTERNS)


def has_confirmation_suffix(content: str) -> bool:
    return _CONFIRMATION_SUFFIX in content.lower()


def talks_about_nano_in_third_person(content: str) -> bool:
    return any(pattern.search(content) for pattern in _THIRD_PERSON_SELF_PATTERNS)


def looks_like_self_description_instead_of_answer(user_message: str, content: str) -> bool:
    lowered_message = user_message.lower()
    if any(trigger in lowered_message for trigger in IDENTITY_OR_CAPABILITY_TRIGGERS):
        return False
    return any(pattern.search(content) for pattern in _SELF_DESCRIPTION_PATTERNS)


def implies_unsupported_continuation(content: str) -> bool:
    return any(pattern.search(content) for pattern in _UNSUPPORTED_CONTINUATION_PATTERNS)


def detect_intent_mismatch(source: ResponseSource, content: str) -> bool:
    if source.kind == "confirmation" and looks_like_refusal(content):
        return True
    if looks_like_refusal(content) and has_confirmation_suffix(content):
        return True
    return False


def detect_violations(user_message: str, content: str) -> list[ViolationKind]:
    violations: list[ViolationKind] = []
    if looks_like_self_description_instead_of_answer(user_message, content):
        violations.append("self_description")
    if implies_unsupported_continuation(content):
        violations.append("unsupported_continuation")
    if talks_about_nano_in_third_person(content):
        violations.append("third_person")
    return violations


def format_source_context(source: ResponseSource) -> str:
    lines = [f"Response kind: {source.kind}"]
    if source.tool_name:
        lines.append(f"Tool: {source.tool_name}")
    lines.append(f"Factual payload: {source.facts}")
    return "\n".join(lines)
