from __future__ import annotations

import logging
import subprocess
import threading
import time
from collections.abc import Callable

from app.config import get_settings
from app.runtime.boot_state import boot_store

logger = logging.getLogger(__name__)

_REBOOT_COMMANDS: tuple[list[str], ...] = (
    ["sudo", "/usr/sbin/reboot"],
    ["sudo", "/bin/systemctl", "reboot"],
)


def _run_commands(commands: tuple[list[str], ...], *, action: str) -> None:
    for command in commands:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                return
            message = (result.stderr or result.stdout or f"{action} failed").strip()
            logger.warning("%s failed (%s): %s", action, " ".join(command), message)
        except OSError as exc:
            logger.warning("%s failed (%s): %s", action, " ".join(command), exc)


def _run_in_background(
    *,
    commands: tuple[list[str], ...],
    thread_name: str,
    action: str,
    delay_seconds: float,
) -> None:
    def _run() -> None:
        time.sleep(delay_seconds)
        _run_commands(commands, action=action)

    thread = threading.Thread(target=_run, name=thread_name, daemon=True)
    thread.start()


def _schedule_when_enabled(
    *,
    enabled: bool,
    disabled_message: str,
    commands: Callable[[], tuple[list[str], ...]],
    thread_name: str,
    action: str,
    delay_seconds: float,
) -> bool:
    if not enabled:
        logger.warning("%s", disabled_message)
        return False

    _run_in_background(
        commands=commands(),
        thread_name=thread_name,
        action=action,
        delay_seconds=delay_seconds,
    )
    return True


def schedule_reboot(*, delay_seconds: float = 1.0) -> bool:
    """Schedule a full Raspberry Pi reboot. Returns False when disabled or scheduling fails."""
    settings = get_settings()
    scheduled = _schedule_when_enabled(
        enabled=settings.reboot_enabled,
        disabled_message="Reboot skipped: REBOOT_ENABLED is false.",
        commands=lambda: _REBOOT_COMMANDS,
        thread_name="nano-reboot",
        action="Reboot",
        delay_seconds=delay_seconds,
    )
    if scheduled:
        boot_store.mark_reboot_pending()
    return scheduled


def schedule_service_restart(*, delay_seconds: float = 1.0) -> bool:
    """Schedule a systemd restart of the nano-core service."""
    settings = get_settings()
    unit = settings.service_unit_name.strip() or "nano-core"
    commands = (["sudo", "/bin/systemctl", "restart", unit],)
    scheduled = _schedule_when_enabled(
        enabled=settings.service_restart_enabled,
        disabled_message="Service restart skipped: SERVICE_RESTART_ENABLED is false.",
        commands=lambda: commands,
        thread_name="nano-service-restart",
        action="Service restart",
        delay_seconds=delay_seconds,
    )
    if scheduled:
        boot_store.mark_restart_pending()
    return scheduled
