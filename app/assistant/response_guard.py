from __future__ import annotations

import json
import re
from typing import Literal

from app.assistant.agent_rules import wipe_confirmation_prompt
from app.assistant.prompts import ALIGNMENT_CHECK_SYSTEM_PROMPT, GUARD_REWRITE_SYSTEM_PROMPT
from app.assistant.response_source import ResponseSource
from app.llm.protocol import LLMClient

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
    "unsupported_continuation": ("Promised unsupported continued work after responding."),
    "third_person": "Referred to Nano in third person instead of first person.",
    "intent_mismatch": ("Refused or contradicted the action Nano is performing or confirming."),
}


def looks_like_refusal(content: str) -> bool:
    """
    Return whether text appears to refuse or decline a request.

    Args:
        content: Text content to inspect.

    Returns:
        True when refusal language is detected.
    """
    return any(pattern.search(content) for pattern in _REFUSAL_PATTERNS)


def has_confirmation_suffix(content: str) -> bool:
    """
    Return whether text includes the destructive-action confirmation suffix.

    Args:
        content: Text content to inspect.

    Returns:
        True when the standard yes/no confirmation suffix is present.
    """
    return _CONFIRMATION_SUFFIX in content.lower()


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


def detect_intent_mismatch(source: ResponseSource, content: str) -> bool:
    """
    Return whether the reply contradicts Nano's intended action.

    Args:
        source: Structured response input.
        content: Candidate assistant reply.

    Returns:
        True when refusal or contradiction is detected.
    """
    if source.kind == "confirmation" and looks_like_refusal(content):
        return True
    if looks_like_refusal(content) and has_confirmation_suffix(content):
        return True
    return False


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


def format_source_context(source: ResponseSource) -> str:
    """
    Format structured response context for alignment and rewrite prompts.

    Args:
        source: Structured response input.

    Returns:
        Multi-line context summary.
    """
    lines = [f"Response kind: {source.kind}"]
    if source.tool_name:
        lines.append(f"Tool: {source.tool_name}")
    lines.append(f"Factual payload: {source.facts}")
    return "\n".join(lines)


def _parse_alignment_response(raw: str) -> dict[str, object] | None:
    stripped = raw.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(lines[1:-1] if len(lines) > 2 else lines).strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def judge_alignment(client: LLMClient, source: ResponseSource, content: str) -> list[str]:
    """
    Ask the LLM whether a reply aligns with Nano's intended action.

    Args:
        client: LLM client used for alignment judging.
        source: Structured response input.
        content: Candidate assistant reply.

    Returns:
        Alignment problem descriptions; empty when aligned or judge fails open.
    """
    messages = [
        {"role": "system", "content": ALIGNMENT_CHECK_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"User request: {source.user_message}\n\n"
                f"Nano intent:\n{format_source_context(source)}\n\n"
                f"Candidate reply:\n{content}"
            ),
        },
    ]
    raw = client.complete(messages=messages).strip()
    payload = _parse_alignment_response(raw)
    if payload is None or "aligned" not in payload:
        return []
    if payload.get("aligned") is True:
        return []
    problems = payload.get("problems", [])
    if not isinstance(problems, list):
        return ["Reply does not align with Nano's intended action."]
    cleaned = [str(problem).strip() for problem in problems if str(problem).strip()]
    return cleaned or ["Reply does not align with Nano's intended action."]


def collect_problems(client: LLMClient, source: ResponseSource, content: str) -> list[str]:
    """
    Collect all guard and alignment problems for a candidate reply.

    Args:
        client: LLM client used for alignment judging.
        source: Structured response input.
        content: Candidate assistant reply.

    Returns:
        Problem descriptions to fix during rewrite.
    """
    problems: list[str] = []
    for violation in detect_violations(source.user_message, content):
        problems.append(_VIOLATION_LABELS[violation])
    if detect_intent_mismatch(source, content):
        problems.append(_VIOLATION_LABELS["intent_mismatch"])
    elif not problems:
        problems.extend(judge_alignment(client, source, content))
    return problems


def rewrite_with_context(
    client: LLMClient,
    source: ResponseSource,
    content: str,
    problems: list[str],
) -> str:
    """
    Rewrite a reply to fix listed guard and alignment problems.

    Args:
        client: LLM client used to revise responses.
        source: Structured response input.
        content: User-facing response content.
        problems: Problem descriptions to fix.

    Returns:
        Revised response content.
    """
    problem_lines = "\n".join(f"- {problem}" for problem in problems)
    messages = [
        {"role": "system", "content": GUARD_REWRITE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"User question: {source.user_message}\n\n"
                f"Nano intent:\n{format_source_context(source)}\n\n"
                f"Previous wrong answer:\n{content}\n\n"
                f"Problems to fix:\n{problem_lines}"
            ),
        },
    ]
    revised = client.complete(messages=messages).strip()
    return revised or content


def enforce_user_facing_answer(
    client: LLMClient,
    source: ResponseSource,
    content: str,
) -> str:
    """
    Apply answer-quality guards to model output intended for the user.

    Args:
        client: LLM client used to revise responses.
        source: Structured response input.
        content: User-facing response content.

    Returns:
        Guarded response content.
    """
    if not content.strip():
        return content

    for _ in range(MAX_GUARD_PASSES):
        problems = collect_problems(client, source, content)
        if not problems:
            break
        content = rewrite_with_context(client, source, content, problems)

    if source.kind == "confirmation" and looks_like_refusal(content):
        content = wipe_confirmation_prompt(source.user_message)
    return content
