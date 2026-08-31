from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock


@dataclass(frozen=True, slots=True)
class BootStateSnapshot:
    id: str
    booted_at: str
    reboot_pending: bool
    restart_pending: bool


class BootStore:
    """In-memory boot identity for the current process."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._boot_id: str | None = None
        self._booted_at: datetime | None = None
        self._reboot_pending = False
        self._restart_pending = False

    def record_boot(self) -> None:
        with self._lock:
            self._boot_id = f"boot_{uuid.uuid4().hex[:20]}"
            self._booted_at = datetime.now(UTC)
            self._reboot_pending = False
            self._restart_pending = False

    def mark_reboot_pending(self) -> None:
        with self._lock:
            self._reboot_pending = True

    def mark_restart_pending(self) -> None:
        with self._lock:
            self._restart_pending = True

    def snapshot(self) -> BootStateSnapshot:
        with self._lock:
            boot_id = self._boot_id or ""
            booted_at = self._booted_at
            return BootStateSnapshot(
                id=boot_id,
                booted_at=booted_at.isoformat() if booted_at is not None else "",
                reboot_pending=self._reboot_pending,
                restart_pending=self._restart_pending,
            )

    def reset(self) -> None:
        with self._lock:
            self._boot_id = None
            self._booted_at = None
            self._reboot_pending = False
            self._restart_pending = False


boot_store = BootStore()
