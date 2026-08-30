from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.system.specs.memory import format_bytes, probe_memory

MEMORY_RESERVE_BYTES = 1_500_000_000
KV_BYTES_PER_TOKEN_ESTIMATE = 131_072


def model_file_size_bytes(model_path: str) -> int | None:
    path = Path(model_path)
    if not path.is_file():
        return None
    return path.stat().st_size


def estimate_max_context_tokens(
    model_path: str,
    *,
    available_bytes: int | None,
    reserve_bytes: int = MEMORY_RESERVE_BYTES,
    kv_bytes_per_token: int = KV_BYTES_PER_TOKEN_ESTIMATE,
) -> int | None:
    if available_bytes is None:
        return None
    model_bytes = model_file_size_bytes(model_path) or 0
    budget = available_bytes - reserve_bytes - model_bytes
    if budget <= 0:
        return None
    return max(0, budget // kv_bytes_per_token)


def collect_system_specs() -> dict[str, Any]:
    settings = get_settings()
    memory = probe_memory()
    chat_model_path = settings.llm_model_path
    chat_model_bytes = model_file_size_bytes(chat_model_path)
    chat_ctx_cap = estimate_max_context_tokens(
        chat_model_path,
        available_bytes=memory.available_bytes,
    )
    return {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "memory": memory.as_dict(),
        "memory_pretty": {
            "total": format_bytes(memory.total_bytes),
            "available": format_bytes(memory.available_bytes),
        },
        "app": {
            "name": settings.app_name,
            "provider_label": _describe_provider(settings.llm_provider),
        },
        "llm": {
            "provider": settings.llm_provider,
            "chat_model_path": chat_model_path,
            "chat_model_label": _friendly_model_label(chat_model_path),
            "chat_model_size_bytes": chat_model_bytes,
            "configured_chat_context": settings.llm_context_size,
            "estimated_chat_context_cap": chat_ctx_cap,
        },
    }


def format_system_analysis_report() -> str:
    specs = collect_system_specs()
    llm = specs["llm"]
    memory = specs["memory"]

    lines = [
        "Here's how I'm running on your machine.",
        "",
        _describe_memory_for_models(memory.get("available_bytes"), memory.get("total_bytes")),
        "",
        f"I run on {_describe_provider(llm['provider'])}.",
        _describe_model_role("everything I do", llm["chat_model_size_bytes"]),
        _describe_context_window(
            llm["configured_chat_context"],
            llm["estimated_chat_context_cap"],
        ),
        "",
        "If memory is tight when I wake up, I'll automatically try a smaller window "
        "and let you know.",
    ]
    return "\n".join(lines)


def _friendly_model_label(model_path: str) -> str:
    name = Path(model_path).name
    if name.endswith(".gguf"):
        name = name[:-5]
    name = name.replace("_", " ").replace("-", " ")
    return name.strip() or model_path


def _describe_provider(provider: str) -> str:
    labels = {
        "local": "your machine — my models stay on your device",
        "ollama": "Ollama on your machine",
        "llama_cpp": "a local model server on your machine",
        "llama_cpp_server": "a local model server on your machine",
        "auto": "your machine first, then other backends if needed",
    }
    return labels.get(provider, provider)


def _describe_memory_for_models(available_bytes: int | None, total_bytes: int | None) -> str:
    if available_bytes is None:
        return "I couldn't read how much memory is free, so I may need to scale down when I start."
    available = format_bytes(available_bytes)
    if available_bytes >= 8_000_000_000:
        tone = "That's plenty for me to run smoothly."
    elif available_bytes >= 4_000_000_000:
        tone = "That should be enough, though I may scale down if memory gets tight."
    else:
        tone = "That's fairly tight — I may need to use a smaller memory window."
    if total_bytes is not None:
        return f"You have {available} free out of {format_bytes(total_bytes)} total. {tone}"
    return f"You have {available} free. {tone}"


def _describe_context_window(configured: int, cap: int | None) -> str:
    if cap is None:
        return "I'm using my full memory window setting."
    if cap >= configured:
        return "I'm using my full memory window setting, and your free RAM supports that."
    return (
        "I'm set for my full memory window, but your free RAM may force a smaller one "
        "unless you close other apps."
    )


def _describe_model_role(role: str, size_bytes: int | None) -> str:
    if size_bytes is None:
        return f"For {role}, my model file is missing — I may not work until that's fixed."
    return f"For {role}, I use a {format_bytes(size_bytes)} model on your device."
