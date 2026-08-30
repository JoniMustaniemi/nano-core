from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from app.config import get_settings


def resolve_completion_options(
    *,
    max_tokens: int | None,
    temperature: float | None,
) -> tuple[int, float]:
    settings = get_settings()
    resolved_max_tokens = max_tokens if max_tokens is not None else settings.llm_max_tokens
    resolved_temperature = temperature if temperature is not None else settings.llm_temperature
    return resolved_max_tokens, resolved_temperature


def unavailable_message() -> str:
    return (
        "Local LLM is not available yet. Install a GGUF model and set "
        "LLM_MODEL_PATH, or point LLM_PROVIDER at a configured backend."
    )


def post_json(
    path: str,
    payload: dict[str, Any],
    *,
    raise_on_error: bool,
) -> httpx.Response | None:
    settings = get_settings()
    try:
        response = httpx.post(
            f"{settings.llm_base_url}{path}",
            json=payload,
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        return response
    except httpx.HTTPError:
        if raise_on_error:
            return None
        return None


def extract_ollama_content(data: dict[str, Any]) -> str | None:
    message = data.get("message", {})
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
    return None


def extract_llama_cpp_content(data: dict[str, Any]) -> str | None:
    choices = data.get("choices", [])
    if isinstance(choices, list) and choices:
        first_choice = choices[0]
        if isinstance(first_choice, dict):
            message = first_choice.get("message", {})
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content
    content = data.get("content")
    if isinstance(content, str) and content.strip():
        return content
    return None


def remote_model_name() -> str:
    return get_settings().llm_model


def ollama_payload(
    messages: Sequence[Mapping[str, str]],
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> dict[str, Any]:
    resolved_max_tokens, resolved_temperature = resolve_completion_options(
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return {
        "model": remote_model_name(),
        "messages": list(messages),
        "stream": False,
        "options": {
            "num_predict": resolved_max_tokens,
            "temperature": resolved_temperature,
        },
    }


def llama_cpp_server_payload(
    messages: Sequence[Mapping[str, str]],
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> dict[str, Any]:
    resolved_max_tokens, resolved_temperature = resolve_completion_options(
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return {
        "model": remote_model_name(),
        "messages": list(messages),
        "stream": False,
        "max_tokens": resolved_max_tokens,
        "temperature": resolved_temperature,
    }
