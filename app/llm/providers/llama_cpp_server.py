from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.llm.providers.shared import (
    extract_llama_cpp_content,
    llama_cpp_server_payload,
    post_json,
)

_LLAMA_CPP_CHAT_PATH = "/v1/chat/completions"


def complete_llama_cpp_server(
    messages: Sequence[Mapping[str, str]],
    *,
    raise_on_error: bool = True,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> str | None:
    payload = llama_cpp_server_payload(
        messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    response = post_json(_LLAMA_CPP_CHAT_PATH, payload, raise_on_error=raise_on_error)
    if response is None:
        return None
    data = response.json()
    content = extract_llama_cpp_content(data)
    if content is not None:
        return content
    return "Local LLM returned an empty response."
