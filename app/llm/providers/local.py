from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.config import get_settings
from app.llm.context_sizing import LocalModelLoadError, load_local_model, pop_context_load_notice
from app.llm.providers.shared import extract_llama_cpp_content, resolve_completion_options


def complete_local(
    messages: Sequence[Mapping[str, str]],
    *,
    raise_on_error: bool = True,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> str | None:
    settings = get_settings()
    model_path = settings.llm_model_path
    if not model_path:
        if raise_on_error:
            return (
                "Local LLM is not available yet. Set LLM_MODEL_PATH to a GGUF "
                "model file and install the local-llm extra."
            )
        return None

    resolved_max_tokens, resolved_temperature = resolve_completion_options(
        max_tokens=max_tokens,
        temperature=temperature,
    )

    try:
        model = load_local_model(model_path, settings.llm_context_size)
        result = model.create_chat_completion(
            messages=list(messages),
            temperature=resolved_temperature,
            max_tokens=resolved_max_tokens,
        )
    except ImportError:
        if raise_on_error:
            return (
                "Local LLM is not available yet. Set LLM_MODEL_PATH to a GGUF "
                "model file and install the local-llm extra."
            )
        return None
    except LocalModelLoadError as exc:
        if raise_on_error:
            return str(exc)
        return None
    except (OSError, ValueError, RuntimeError):
        if raise_on_error:
            return (
                "Local LLM is not available yet. Set LLM_MODEL_PATH to a GGUF "
                "model file and install the local-llm extra."
            )
        return None

    content = extract_llama_cpp_content(result)
    if content is None:
        return "Local LLM returned an empty response."
    notice = pop_context_load_notice(model_path)
    if notice:
        return f"{notice}\n\n{content}"
    return content
