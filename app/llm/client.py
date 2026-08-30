from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.config import get_settings
from app.llm.providers import auto, llama_cpp_server, local, ollama
from app.llm.providers.shared import unavailable_message


class LocalLLMClient:
    def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        settings = get_settings()

        if settings.llm_provider == "local":
            return (
                local.complete_local(
                    messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                or unavailable_message()
            )
        if settings.llm_provider == "ollama":
            return (
                ollama.complete_ollama(
                    messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                or unavailable_message()
            )
        if settings.llm_provider in {"llama_cpp", "llama_cpp_server"}:
            return (
                llama_cpp_server.complete_llama_cpp_server(
                    messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                or unavailable_message()
            )

        return auto.complete_auto(
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
