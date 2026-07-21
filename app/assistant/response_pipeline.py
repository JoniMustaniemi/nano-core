from __future__ import annotations

from app.assistant.response_composer import ResponseComposer
from app.assistant.response_guard import enforce_user_facing_answer
from app.assistant.response_polish import polish_user_facing_answer
from app.assistant.response_source import ResponseSource
from app.llm.protocol import LLMClient
from app.memory import repository
from app.runtime.activity import activity


def finalize_response(
    client: LLMClient,
    source: ResponseSource,
    *,
    composer: ResponseComposer,
    standby_detail: str = "The response is ready.",
    standby_source: str = "assistant.response_pipeline",
) -> str:
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
        content = composer.compose(client, source)
        content = enforce_user_facing_answer(client, source, content)
        content = polish_user_facing_answer(client, source, content)
        if source.persist:
            repository.add_chat_message(
                conversation_id=source.conversation_id,
                role="assistant",
                content=content,
            )
        return content
    finally:
        activity.standby(
            title="Nano is back in standby.",
            detail=standby_detail,
            source=standby_source,
        )
