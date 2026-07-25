from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.system.specs import (
    KV_BYTES_PER_TOKEN_ESTIMATE,
    MEMORY_RESERVE_BYTES,
    estimate_max_context_tokens,
    format_bytes,
    probe_memory,
)

CONTEXT_SIZE_LADDER: tuple[int, ...] = (
    32768,
    16384,
    8192,
    4096,
    2048,
    1024,
    512,
)

_load_notices: dict[str, str] = {}


class LocalModelLoadError(RuntimeError):
    """Raised when a local GGUF model cannot be loaded at any context size."""


def pop_context_load_notice(model_path: str) -> str | None:
    return _load_notices.pop(model_path, None)


def _set_context_load_notice(model_path: str, message: str) -> None:
    _load_notices[model_path] = message


def format_context_downgrade_notice(
    model_path: str,
    requested: int,
    resolved: int,
    *,
    reason: str,
) -> str:
    if resolved >= requested:
        return ""
    if reason == "memory":
        detail = "your free memory was too low"
    else:
        detail = "I couldn't load at my full setting"
    return f"I had to use a smaller memory window ({detail}), but I'm running."


def context_sizes_to_try(model_path: str, requested_context_size: int) -> list[int]:
    requested = max(512, requested_context_size)
    ladder = [size for size in CONTEXT_SIZE_LADDER if size <= requested]
    if not ladder:
        ladder = [512]
    memory = probe_memory()
    ram_cap = estimate_max_context_tokens(
        model_path,
        available_bytes=memory.available_bytes,
        reserve_bytes=MEMORY_RESERVE_BYTES,
        kv_bytes_per_token=KV_BYTES_PER_TOKEN_ESTIMATE,
    )
    if ram_cap is not None:
        ladder = [size for size in ladder if size <= ram_cap]
        if not ladder:
            ladder = [512]
    return ladder


def _create_llama_model(model_path: str, context_size: int) -> Any:
    try:
        from llama_cpp import Llama
    except ImportError as exc:  # pragma: no cover - depends on optional install
        raise ImportError(
            "llama-cpp-python is not installed. Install the local-llm extra."
        ) from exc
    return Llama(model_path=model_path, n_ctx=context_size, verbose=False)


def _load_local_model_uncached(model_path: str, requested_context_size: int) -> tuple[Any, int]:
    sizes = context_sizes_to_try(model_path, requested_context_size)
    errors: list[str] = []
    attempted_failure = False
    for context_size in sizes:
        try:
            model = _create_llama_model(model_path, context_size)
            if context_size < requested_context_size:
                reason = "load_failure" if attempted_failure else "memory"
                notice = format_context_downgrade_notice(
                    model_path,
                    requested_context_size,
                    context_size,
                    reason=reason,
                )
                if notice:
                    _set_context_load_notice(model_path, notice)
            return model, context_size
        except ImportError:
            raise
        except (OSError, RuntimeError, ValueError) as exc:
            errors.append(f"{context_size}: {exc}")
            attempted_failure = True
            continue

    memory = probe_memory()
    from app.system.specs import model_file_size_bytes

    model_bytes = model_file_size_bytes(model_path)
    model_hint = format_bytes(model_bytes)
    available_hint = format_bytes(memory.available_bytes)
    attempted = ", ".join(str(size) for size in sizes)
    detail = "; ".join(errors[-3:])
    raise LocalModelLoadError(
        "Local LLM could not load "
        f"{model_path} ({model_hint}) with available memory {available_hint}. "
        f"Tried context sizes {attempted}. {detail}".strip()
    )


@lru_cache(maxsize=8)
def load_local_model(model_path: str, requested_context_size: int) -> Any:
    model, _resolved = _load_local_model_uncached(model_path, requested_context_size)
    return model
