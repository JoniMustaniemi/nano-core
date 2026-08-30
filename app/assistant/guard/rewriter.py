from __future__ import annotations

import json

from app.assistant.guard.detectors import (
    _VIOLATION_LABELS,
    MAX_GUARD_PASSES,
    detect_intent_mismatch,
    detect_violations,
    format_source_context,
    looks_like_refusal,
)
from app.assistant.prompts import ALIGNMENT_CHECK_SYSTEM_PROMPT, GUARD_REWRITE_SYSTEM_PROMPT
from app.assistant.response_source import ResponseSource
from app.assistant.rules import wipe_confirmation_prompt
from app.llm.protocol import LLMClient


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
    messages = [
        {"role": "system", "content": ALIGNMENT_CHECK_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"User request: {source.user_message}\n\n"
                f"Intended action:\n{format_source_context(source)}\n\n"
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
        return ["Reply does not align with your intended action."]
    cleaned = [str(problem).strip() for problem in problems if str(problem).strip()]
    return cleaned or ["Reply does not align with your intended action."]


def collect_problems(client: LLMClient, source: ResponseSource, content: str) -> list[str]:
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
    problem_lines = "\n".join(f"- {problem}" for problem in problems)
    messages = [
        {"role": "system", "content": GUARD_REWRITE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"User question: {source.user_message}\n\n"
                f"Intended action:\n{format_source_context(source)}\n\n"
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
    if not content.strip() or source.skip_enrichment:
        return content

    for _ in range(MAX_GUARD_PASSES):
        problems = collect_problems(client, source, content)
        if not problems:
            break
        content = rewrite_with_context(client, source, content, problems)

    if source.kind == "confirmation" and looks_like_refusal(content):
        content = wipe_confirmation_prompt(source.user_message)
    return content
