from __future__ import annotations

from typing import Any

from app.assistant.capabilities import list_capability_items
from app.assistant.response_variation import choose_variation_hint
from app.assistant.rules.intents import is_identity_question


def count_prior_identity_questions_in_history(history: list[Any]) -> int:
    """
    Count identity questions in history before the current turn.

    Args:
        history: Conversation history records including the current user message.

    Returns:
        Number of earlier user messages that asked about identity.
    """
    count = 0
    for entry in history:
        if getattr(entry, "role", "") != "user":
            continue
        content = str(getattr(entry, "content", ""))
        if is_identity_question(content):
            count += 1
    return max(0, count - 1)


def format_identity_payload(*, message: str, history: list[Any]) -> str:
    """
    Build factual identity context for dynamic answer drafting.

    Args:
        message: Current user message.
        history: Conversation history records.

    Returns:
        Multi-line factual payload for the identity answer prompt.
    """
    capability_names = ", ".join(item.name for item in list_capability_items())
    prior_identity_questions = count_prior_identity_questions_in_history(history)
    conversation_lines = [f"- Current question: {message.strip()}"]
    if prior_identity_questions:
        conversation_lines.append(
            "- The user has asked about your identity before in this conversation. "
            "Use noticeably different wording from earlier replies."
        )
    else:
        conversation_lines.append("- First identity question in this conversation.")

    return "\n".join(
        [
            "Core identity facts:",
            "- Name: Nano",
            "- Role: personal assistant with a clinical, sarcastic overseer personality",
            "- Operating style: detached, analytical, efficient; help is your function",
            "- Voice: first person only; dry, precise, faintly condescending; never apologetic",
            "",
            f"Registered capability names: {capability_names}",
            "",
            "Conversation context:",
            *conversation_lines,
            "",
            "Variation guidance:",
            f"- {choose_variation_hint()}",
        ]
    )
