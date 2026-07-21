from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ResponseKind = Literal["answer", "tool_result", "tool_error", "follow_up", "confirmation"]


@dataclass(frozen=True)
class ResponseSource:
    """
    Structured facts produced before composition and guarding.

    Compose strategy by kind:
    - answer: pass-through (draft already uses SYSTEM_PROMPT)
    - follow_up: pass-through
    - confirmation: LLM wording for wipe prompts; pass-through otherwise
    - tool_result: deterministic for health; hinted/LLM for JSON payloads
    - tool_error: LLM for JSON payloads; pass-through for plain text
    """

    kind: ResponseKind
    user_message: str
    facts: str
    tool_name: str | None = None
    conversation_id: str = "default"
    persist: bool = True


def answer_source(
    *,
    user_message: str,
    facts: str,
    conversation_id: str = "default",
    persist: bool = True,
) -> ResponseSource:
    """
    Build an answer response source from a factual draft.

    Args:
        user_message: Original user message.
        facts: Tone-neutral factual draft.
        conversation_id: Conversation identifier.

    Returns:
        ResponseSource for composition.
    """
    return ResponseSource(
        kind="answer",
        user_message=user_message,
        facts=facts,
        conversation_id=conversation_id,
        persist=persist,
    )


def follow_up_source(
    *,
    user_message: str,
    facts: str,
    conversation_id: str = "default",
) -> ResponseSource:
    """
    Build a follow-up response source.

    Args:
        user_message: Original user message.
        facts: Follow-up question or prompt text.
        conversation_id: Conversation identifier.

    Returns:
        ResponseSource for composition.
    """
    return ResponseSource(
        kind="follow_up",
        user_message=user_message,
        facts=facts,
        conversation_id=conversation_id,
    )


def confirmation_source(
    *,
    user_message: str,
    facts: str,
    conversation_id: str = "default",
) -> ResponseSource:
    """
    Build a confirmation response source.

    Args:
        user_message: Original user message.
        facts: Confirmation context or draft text.
        conversation_id: Conversation identifier.

    Returns:
        ResponseSource for composition.
    """
    return ResponseSource(
        kind="confirmation",
        user_message=user_message,
        facts=facts,
        conversation_id=conversation_id,
    )


def tool_result_source(
    *,
    user_message: str,
    facts: str,
    tool_name: str,
    conversation_id: str = "default",
) -> ResponseSource:
    """
    Build a tool result response source.

    Args:
        user_message: Original user message.
        facts: Serialized or plain tool output.
        tool_name: Registered tool name.
        conversation_id: Conversation identifier.

    Returns:
        ResponseSource for composition.
    """
    return ResponseSource(
        kind="tool_result",
        user_message=user_message,
        facts=facts,
        tool_name=tool_name,
        conversation_id=conversation_id,
    )


def tool_error_source(
    *,
    user_message: str,
    facts: str,
    tool_name: str,
    conversation_id: str = "default",
) -> ResponseSource:
    """
    Build a tool error response source.

    Args:
        user_message: Original user message.
        facts: Structured error detail.
        tool_name: Registered tool name.
        conversation_id: Conversation identifier.

    Returns:
        ResponseSource for composition.
    """
    return ResponseSource(
        kind="tool_error",
        user_message=user_message,
        facts=facts,
        tool_name=tool_name,
        conversation_id=conversation_id,
    )
