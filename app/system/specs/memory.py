from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


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
