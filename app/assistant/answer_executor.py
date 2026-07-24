from __future__ import annotations

from typing import Any

from app.assistant.capabilities import format_capability_catalog
from app.assistant.identity_context import format_identity_payload
from app.assistant.prompts import (
    CAPABILITIES_ANSWER_PROMPT,
    IDENTITY_ANSWER_PROMPT,
    SYSTEM_PROMPT,
)
from app.assistant.response_source import ResponseSource, answer_source
from app.assistant.response_variation import choose_variation_hint
from app.llm.protocol import LLMClient
from app.runtime.activity import activity
from app.runtime.status_copy import (
    ANSWERING_DETAIL,
    ANSWERING_TITLE,
    DRAFTING_IDENTITY_DETAIL,
    INTRODUCING_TITLE,
    REVIEWING_CAPABILITIES_DETAIL,
    REVIEWING_CAPABILITIES_TITLE,
)


class AnswerExecutor:
    """
    Build factual answer drafts without applying final personality.
    """

    def draft(
        self,
        *,
        client: LLMClient,
        message: str,
        conversation_id: str,
        history: list[Any],
    ) -> ResponseSource:
        """
        Draft a direct answer from conversation context.

        Args:
            client: LLM client used to draft the answer.
            message: User message text.
            conversation_id: Conversation identifier.
            history: Conversation history records.

        Returns:
            Answer response source with a factual draft.
        """
        activity.working(
            title=ANSWERING_TITLE,
            detail=ANSWERING_DETAIL,
            source="assistant.answer_executor",
        )
        fallback_messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for entry in history:
            fallback_messages.append({"role": entry.role, "content": entry.content})
        if not history or history[-1].role != "user" or history[-1].content != message:
            fallback_messages.append({"role": "user", "content": message})
        content = client.complete(messages=fallback_messages).strip()
        return answer_source(
            user_message=message,
            facts=content,
            conversation_id=conversation_id,
        )

    def draft_capabilities(
        self,
        *,
        client: LLMClient,
        message: str,
        conversation_id: str,
    ) -> ResponseSource:
        """
        Draft a capabilities answer from the current tool catalog.

        Args:
            client: LLM client used to draft the answer.
            message: User message text.
            conversation_id: Conversation identifier.

        Returns:
            Answer response source with a factual draft.
        """
        activity.working(
            title=REVIEWING_CAPABILITIES_TITLE,
            detail=REVIEWING_CAPABILITIES_DETAIL,
            source="assistant.answer_executor",
        )
        catalog = format_capability_catalog()
        messages = [
            {"role": "system", "content": CAPABILITIES_ANSWER_PROMPT},
            {
                "role": "user",
                "content": (
                    f"User question: {message}\n\n"
                    f"Factual payload:\n{catalog}\n\n"
                    f"Variation guidance:\n- {choose_variation_hint()}"
                ),
            },
        ]
        content = client.complete(messages=messages).strip()
        if not content:
            content = catalog
        return answer_source(
            user_message=message,
            facts=content,
            conversation_id=conversation_id,
        )

    def draft_identity(
        self,
        *,
        client: LLMClient,
        message: str,
        conversation_id: str,
        history: list[Any],
    ) -> ResponseSource:
        """
        Draft an identity answer with dynamic context and varied phrasing.

        Args:
            client: LLM client used to draft the answer.
            message: User message text.
            conversation_id: Conversation identifier.
            history: Conversation history records.

        Returns:
            Answer response source with a factual draft.
        """
        activity.working(
            title=INTRODUCING_TITLE,
            detail=DRAFTING_IDENTITY_DETAIL,
            source="assistant.answer_executor",
        )
        payload = format_identity_payload(message=message, history=history)
        messages = [
            {"role": "system", "content": IDENTITY_ANSWER_PROMPT},
            {
                "role": "user",
                "content": (f"User question: {message}\n\nFactual payload:\n{payload}"),
            },
        ]
        content = client.complete(messages=messages).strip()
        if not content:
            content = "I am Nano. State your business."
        return answer_source(
            user_message=message,
            facts=content,
            conversation_id=conversation_id,
        )

    def draft_wake(self, *, client: LLMClient) -> ResponseSource:
        """
        Draft a wake acknowledgment without final personality polish.

        Args:
            client: LLM client used to draft the wake response.

        Returns:
            Answer response source for wake composition.
        """
        from app.assistant.prompts import WAKE_RESPONSE_SYSTEM_PROMPT

        messages = [
            {"role": "system", "content": WAKE_RESPONSE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "The user said your wake phrase and is waiting for acknowledgment.",
            },
        ]
        content = client.complete(messages=messages).strip()
        if not content:
            content = "I am listening. Proceed."
        return answer_source(
            user_message="wake phrase",
            facts=content,
            conversation_id="wake",
            persist=False,
        )
