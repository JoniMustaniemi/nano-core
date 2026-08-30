from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.llm.providers import llama_cpp_server, local, ollama
from app.llm.providers.shared import unavailable_message


def complete_auto(
    messages: Sequence[Mapping[str, str]],
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> str:
    for complete in (
        local.complete_local,
        ollama.complete_ollama,
        llama_cpp_server.complete_llama_cpp_server,
    ):
        content = complete(
            messages,
            raise_on_error=False,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if content is not None:
            return content
    return unavailable_message()
