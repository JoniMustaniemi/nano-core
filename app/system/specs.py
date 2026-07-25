from __future__ import annotations

import json
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import get_settings

MEMORY_RESERVE_BYTES = 1_500_000_000
KV_BYTES_PER_TOKEN_ESTIMATE = 131_072


@dataclass(frozen=True, slots=True)
class MemoryInfo:
    total_bytes: int | None
    available_bytes: int | None

    def as_dict(self) -> dict[str, int | None]:
        return {
            "total_bytes": self.total_bytes,
            "available_bytes": self.available_bytes,
        }


def format_bytes(value: int | None) -> str:
    if value is None:
        return "unknown"
    if value >= 1_073_741_824:
        return f"{value / 1_073_741_824:.1f} GB"
    if value >= 1_048_576:
        return f"{value / 1_048_576:.0f} MB"
    return f"{value / 1024:.0f} KB"


def probe_memory() -> MemoryInfo:
    """
    Return total and available physical memory when the host exposes it.

    Returns:
        Memory totals for the current machine.
    """
    if sys.platform == "win32":
        return _probe_memory_windows()
    if sys.platform == "darwin":
        return _probe_memory_macos()
    return _probe_memory_unix()


def _probe_memory_windows() -> MemoryInfo:
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        win_dll = getattr(ctypes, "WinDLL", None)
        if win_dll is None:
            return MemoryInfo(total_bytes=None, available_bytes=None)
        kernel32 = win_dll("kernel32", use_last_error=True)
        if not kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return MemoryInfo(total_bytes=None, available_bytes=None)
        return MemoryInfo(
            total_bytes=int(status.ullTotalPhys),
            available_bytes=int(status.ullAvailPhys),
        )
    except (AttributeError, OSError, ValueError):
        return MemoryInfo(total_bytes=None, available_bytes=None)


def _probe_memory_unix() -> MemoryInfo:
    proc_path = Path("/proc/meminfo")
    if not proc_path.exists():
        return MemoryInfo(total_bytes=None, available_bytes=None)
    try:
        values: dict[str, int] = {}
        for line in proc_path.read_text(encoding="utf-8").splitlines():
            name, raw_value = line.split(":", maxsplit=1)
            values[name.strip()] = int(raw_value.strip().split()[0]) * 1024
        total = values.get("MemTotal")
        available = values.get("MemAvailable") or values.get("MemFree")
        return MemoryInfo(total_bytes=total, available_bytes=available)
    except (OSError, ValueError):
        return MemoryInfo(total_bytes=None, available_bytes=None)


def _probe_memory_macos() -> MemoryInfo:
    try:
        import ctypes
        import ctypes.util

        libc = ctypes.CDLL(ctypes.util.find_library("c"))
        memsize = ctypes.c_uint64()
        if (
            libc.sysctlbyname(
                "hw.memsize", ctypes.byref(memsize), ctypes.byref(ctypes.c_uint64(8)), None, 0
            )
            != 0
        ):
            return MemoryInfo(total_bytes=None, available_bytes=None)
        total = int(memsize.value)
        sysconf = getattr(os, "sysconf", None)
        if sysconf is None:
            return MemoryInfo(total_bytes=None, available_bytes=None)
        page_size = int(sysconf("SC_PAGE_SIZE"))
        free_pages = int(sysconf("SC_AVPHYS_PAGES"))
        available = free_pages * page_size
        return MemoryInfo(total_bytes=total, available_bytes=available)
    except (AttributeError, OSError, ValueError, TypeError):
        return MemoryInfo(total_bytes=None, available_bytes=None)


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
    code_model_path = settings.llm_code_model_path or settings.llm_model_path
    chat_model_bytes = model_file_size_bytes(chat_model_path)
    code_model_bytes = model_file_size_bytes(code_model_path)
    chat_ctx_cap = estimate_max_context_tokens(
        chat_model_path,
        available_bytes=memory.available_bytes,
    )
    code_ctx_cap = estimate_max_context_tokens(
        code_model_path,
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
            "code_model_path": code_model_path,
            "chat_model_label": _friendly_model_label(chat_model_path),
            "code_model_label": _friendly_model_label(code_model_path),
            "same_brain": chat_model_path == code_model_path,
            "chat_model_size_bytes": chat_model_bytes,
            "code_model_size_bytes": code_model_bytes,
            "configured_chat_context": settings.llm_context_size,
            "configured_code_context": settings.llm_code_context_size,
            "estimated_chat_context_cap": chat_ctx_cap,
            "estimated_code_context_cap": code_ctx_cap,
        },
    }


def _friendly_model_label(model_path: str) -> str:
    name = Path(model_path).name
    if name.endswith(".gguf"):
        name = name[:-5]
    name = name.replace("_", " ").replace("-", " ")
    return name.strip() or model_path


def _format_context_k(tokens: int) -> str:
    if tokens >= 1024 and tokens % 1024 == 0:
        return f"{tokens // 1024}k"
    return f"{tokens:,}"


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


def format_system_analysis_report() -> str:
    specs = collect_system_specs()
    llm = specs["llm"]
    memory = specs["memory"]

    chat_path = llm["chat_model_path"]
    code_path = llm["code_model_path"]
    same_brain = chat_path == code_path

    lines = [
        "Here's how I'm running on your machine.",
        "",
        _describe_memory_for_models(memory.get("available_bytes"), memory.get("total_bytes")),
        "",
        f"I run on {_describe_provider(llm['provider'])}.",
    ]

    if same_brain:
        lines.append(_describe_model_role("everything I do", llm["chat_model_size_bytes"]))
        lines.append(
            _describe_context_window(
                llm["configured_chat_context"],
                llm["estimated_chat_context_cap"],
            )
        )
    else:
        lines.append(_describe_model_role("talking with you", llm["chat_model_size_bytes"]))
        lines.append(
            _describe_context_window(
                llm["configured_chat_context"],
                llm["estimated_chat_context_cap"],
            )
        )
        lines.append(_describe_model_role("code and planning work", llm["code_model_size_bytes"]))
        if llm["configured_code_context"] != llm["configured_chat_context"] or (
            llm["estimated_code_context_cap"] != llm["estimated_chat_context_cap"]
        ):
            lines.append(
                _describe_context_window(
                    llm["configured_code_context"],
                    llm["estimated_code_context_cap"],
                )
            )

    lines.append("")
    lines.append(
        "If memory is tight when I wake up, I'll automatically try a smaller window "
        "and let you know."
    )
    return "\n".join(lines)


def format_system_analysis_json() -> str:
    return json.dumps(collect_system_specs(), indent=2)
