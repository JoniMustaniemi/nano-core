from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.llm.providers.shared import (
    extract_ollama_content,
    ollama_payload,
    post_json,
)

_OLLAMA_CHAT_PATH = "/api/chat"


def complete_ollama(
    messages: Sequence[Mapping[str, str]],
    *,
    raise_on_error: bool = True,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> str | None:
    payload = ollama_payload(
        messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    response = post_json(_OLLAMA_CHAT_PATH, payload, raise_on_error=raise_on_error)
    if response is None:
        return None
    data = response.json()
    content = extract_ollama_content(data)
    if content is not None:
        return content
    return "Local LLM returned an empty response."
