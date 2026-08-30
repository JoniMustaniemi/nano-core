from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

_THERMAL_ZONE_PATH = Path("/sys/class/thermal/thermal_zone0/temp")


def probe_cpu_temperature() -> float | None:
    temp = _probe_cpu_temperature_sysfs(_THERMAL_ZONE_PATH)
    if temp is not None:
        return temp
    return _probe_cpu_temperature_vcgencmd()


def probe_cpu_throttled() -> bool | None:
    return _probe_cpu_throttled_vcgencmd()


def serialize_system_metrics() -> dict[str, float | bool | None]:
    return {
        "cpu_temperature_celsius": probe_cpu_temperature(),
        "throttled": probe_cpu_throttled(),
    }


def _probe_cpu_temperature_sysfs(path: Path) -> float | None:
    if not path.is_file():
        return None
    try:
        millidegrees = int(path.read_text(encoding="utf-8").strip())
        return round(millidegrees / 1000, 1)
    except (OSError, ValueError):
        return None


def _probe_cpu_temperature_vcgencmd() -> float | None:
    if shutil.which("vcgencmd") is None:
        return None
    try:
        result = subprocess.run(
            ["vcgencmd", "measure_temp"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    match = re.search(r"temp=([\d.]+)'?C", result.stdout)
    if match is None:
        return None
    return round(float(match.group(1)), 1)


def _probe_cpu_throttled_vcgencmd() -> bool | None:
    if shutil.which("vcgencmd") is None:
        return None
    try:
        result = subprocess.run(
            ["vcgencmd", "get_throttled"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    match = re.search(r"throttled=(0x[0-9a-fA-F]+)", result.stdout)
    if match is None:
        return None
    value = int(match.group(1), 16)
    return bool(value & 0xC)
