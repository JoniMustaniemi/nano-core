from __future__ import annotations

from app.assistant.response_composer import ResponseComposer
from app.assistant.response_guard import enforce_user_facing_answer
from app.assistant.response_polish import polish_user_facing_answer
from app.assistant.response_source import ResponseSource
from app.llm.protocol import LLMClient
from app.memory import repository
from app.runtime.activity import activity
from app.runtime.status_copy import (
    COMPOSING_DETAIL,
    COMPOSING_TITLE,
    STANDBY_DETAIL_WAITING,
    choose_standby_greeting,
)


def finalize_response(
    client: LLMClient,
    source: ResponseSource,
    *,
    composer: ResponseComposer,
    standby_detail: str = STANDBY_DETAIL_WAITING,
    standby_source: str = "assistant.response_pipeline",
) -> tuple[str, bool]:
    """
    Compose, guard, polish, persist, and return a user-facing assistant reply.

    Args:
        client: LLM client used for composition and guarding.
        source: Structured response input.
        composer: Response composer instance.
        standby_detail: Activity detail shown when returning to standby.
        standby_source: Activity source label.

    Returns:
        Final user-facing assistant text.
    """
    try:
        activity.working(
            title=COMPOSING_TITLE,
            detail=COMPOSING_DETAIL,
            source=standby_source,
        )
        content = composer.compose(client, source)
        content = enforce_user_facing_answer(client, source, content)
        content = polish_user_facing_answer(client, source, content)
        if source.persist:
            repository.add_chat_message(
                conversation_id=source.conversation_id,
                role="assistant",
                content=content,
            )
        return content, source.speak
    finally:
        activity.standby(
            title=choose_standby_greeting(),
            detail=None,
            source=standby_source,
        )
