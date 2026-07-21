from __future__ import annotations

from typing import Any, cast

from app.assistant.prompts import SYSTEM_PROMPT
from app.assistant.response_source import ResponseSource, answer_source
from app.runtime.activity import activity


class AnswerExecutor:
    """
    Build factual answer drafts without applying final personality.
    """

    def draft(
        self,
        *,
        client: Any,
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
            title="Nano is answering.",
            detail="Using plain chat mode with the local model.",
            source="assistant.answer_executor",
        )
        fallback_messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for entry in history:
            fallback_messages.append({"role": entry.role, "content": entry.content})
        if not history or history[-1].role != "user" or history[-1].content != message:
            fallback_messages.append({"role": "user", "content": message})
        content = cast(str, client.complete(messages=fallback_messages)).strip()
        activity.standby(
            title="Nano answered without tools.",
            detail="Drafted a direct answer for composition.",
            source="assistant.answer_executor",
        )
        return answer_source(
            user_message=message,
            facts=content,
            conversation_id=conversation_id,
        )

    def draft_wake(self, *, client: Any) -> ResponseSource:
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
        content = cast(str, client.complete(messages=messages)).strip()
        if not content:
            content = "I am listening. Proceed."
        return answer_source(
            user_message="wake phrase",
            facts=content,
            conversation_id="wake",
        )
