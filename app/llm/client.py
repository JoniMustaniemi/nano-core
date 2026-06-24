from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import lru_cache
from typing import Any

import httpx

from app.config import get_settings

_OLLAMA_CHAT_PATH = "/api/chat"
_LLAMA_CPP_CHAT_PATH = "/v1/chat/completions"


class LocalLLMClient:
    def complete(self, messages: Sequence[Mapping[str, str]]) -> str:
        """
        Complete the requested operation.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        settings = get_settings()

        if settings.llm_provider == "local":
            return self._complete_local(messages) or self._unavailable_message()
        if settings.llm_provider == "ollama":
            return self._complete_ollama(messages) or self._unavailable_message()
        if settings.llm_provider in {"llama_cpp", "llama_cpp_server"}:
            return self._complete_llama_cpp_server(messages) or self._unavailable_message()

        return self._complete_auto(messages)

    def _complete_auto(self, messages: Sequence[Mapping[str, str]]) -> str:
        """
        Complete auto.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        for complete in (
            self._complete_local,
            self._complete_ollama,
            self._complete_llama_cpp_server,
        ):
            content = complete(messages, raise_on_error=False)
            if content is not None:
                return content
        return self._unavailable_message()

    def _unavailable_message(self) -> str:
        """
        Handle unavailable message.

        Returns:
            Generated or formatted string value.
        """
        return (
            "Local LLM is not available yet. Install a GGUF model and set "
            "LLM_MODEL_PATH, or point LLM_PROVIDER at a configured backend."
        )

    def _complete_local(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        raise_on_error: bool = True,
    ) -> str | None:
        """
        Complete local.

        Args:
            messages: Conversation messages to send to the model.
            raise_on_error: Raise on error value.

        Returns:
            Parsed value when available; otherwise None.
        """
        settings = get_settings()
        if not settings.llm_model_path:
            if raise_on_error:
                return (
                    "Local LLM is not available yet. Set LLM_MODEL_PATH to a GGUF "
                    "model file and install the local-llm extra."
                )
            return None

        try:
            model = _load_local_model(
                settings.llm_model_path,
                settings.llm_context_size,
            )
            result = model.create_chat_completion(
                messages=list(messages),
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )
        except (ImportError, OSError, ValueError, RuntimeError):
            if raise_on_error:
                return (
                    "Local LLM is not available yet. Set LLM_MODEL_PATH to a GGUF "
                    "model file and install the local-llm extra."
                )
            return None

        content = self._extract_llama_cpp_content(result)
        if content is not None:
            return content
        return "Local LLM returned an empty response."

    def _complete_ollama(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        raise_on_error: bool = True,
    ) -> str | None:
        """
        Complete ollama.

        Args:
            messages: Conversation messages to send to the model.
            raise_on_error: Raise on error value.

        Returns:
            Parsed value when available; otherwise None.
        """
        payload = self._ollama_payload(messages)
        response = self._post(_OLLAMA_CHAT_PATH, payload, raise_on_error=raise_on_error)
        if response is None:
            return None
        data = response.json()
        content = self._extract_ollama_content(data)
        if content is not None:
            return content
        return "Local LLM returned an empty response."

    def _complete_llama_cpp_server(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        raise_on_error: bool = True,
    ) -> str | None:
        """
        Complete llama cpp server.

        Args:
            messages: Conversation messages to send to the model.
            raise_on_error: Raise on error value.

        Returns:
            Parsed value when available; otherwise None.
        """
        payload = self._llama_cpp_server_payload(messages)
        response = self._post(_LLAMA_CPP_CHAT_PATH, payload, raise_on_error=raise_on_error)
        if response is None:
            return None
        data = response.json()
        content = self._extract_llama_cpp_content(data)
        if content is not None:
            return content
        return "Local LLM returned an empty response."

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        raise_on_error: bool,
    ) -> httpx.Response | None:
        """
        Post the requested operation.

        Args:
            path: Path value.
            payload: Validated request payload.
            raise_on_error: Raise on error value.

        Returns:
            Parsed value when available; otherwise None.
        """
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

    def _ollama_payload(self, messages: Sequence[Mapping[str, str]]) -> dict[str, Any]:
        """
        Handle ollama payload.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Dictionary containing the requested data.
        """
        settings = get_settings()
        return {
            "model": settings.llm_model,
            "messages": list(messages),
            "stream": False,
        }

    def _llama_cpp_server_payload(
        self,
        messages: Sequence[Mapping[str, str]],
    ) -> dict[str, Any]:
        """
        Handle llama cpp server payload.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Dictionary containing the requested data.
        """
        settings = get_settings()
        return {
            "model": settings.llm_model,
            "messages": list(messages),
            "stream": False,
        }

    def _extract_ollama_content(self, data: dict[str, Any]) -> str | None:
        """
        Extract ollama content.

        Args:
            data: Response payload returned by the backend.

        Returns:
            Parsed value when available; otherwise None.
        """
        message = data.get("message", {})
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content
        return None

    def _extract_llama_cpp_content(self, data: dict[str, Any]) -> str | None:
        """
        Extract llama cpp content.

        Args:
            data: Response payload returned by the backend.

        Returns:
            Parsed value when available; otherwise None.
        """
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


@lru_cache(maxsize=4)
def _load_local_model(model_path: str, context_size: int) -> Any:
    """
    Load local model.

    Args:
        model_path: Filesystem path to the local model file.
        context_size: Context size value.

    Returns:
        Any result.

    Raises:
        ImportError: If the operation cannot be completed.
    """
    try:
        from llama_cpp import Llama
    except ImportError as exc:  # pragma: no cover - depends on optional install
        raise ImportError(
            "llama-cpp-python is not installed. Install the local-llm extra."
        ) from exc

    return Llama(model_path=model_path, n_ctx=context_size, verbose=False)
