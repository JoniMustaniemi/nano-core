from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock

from app.deploy.update import UpdateCheckResult


@dataclass(frozen=True, slots=True)
class UpdateStateSnapshot:
    available: bool
    commits_behind: int | None
    remote_sha: str | None
    local_sha: str | None
    branch: str | None
    last_checked_at: str | None
    message: str | None


class UpdateStore:
    """In-memory update prompt state for the current service session."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._session_baseline_sha: str | None = None
        self._dismissed_remote_sha: str | None = None
        self._last_check: UpdateCheckResult | None = None
        self._last_checked_at: datetime | None = None
        self._prompt_offered_for_sha: str | None = None

    def set_session_baseline(self, remote_sha: str | None) -> None:
        with self._lock:
            self._session_baseline_sha = remote_sha

    def record_check(self, result: UpdateCheckResult) -> None:
        with self._lock:
            self._last_check = result
            self._last_checked_at = datetime.now(UTC)

    def dismiss(self, remote_sha: str) -> None:
        with self._lock:
            self._dismissed_remote_sha = remote_sha
            self._prompt_offered_for_sha = None

    def mark_prompt_offered(self, remote_sha: str) -> None:
        with self._lock:
            self._prompt_offered_for_sha = remote_sha

    def should_prompt(self, remote_sha: str) -> bool:
        with self._lock:
            if not remote_sha:
                return False
            if remote_sha == self._dismissed_remote_sha:
                return False
            if remote_sha == self._prompt_offered_for_sha:
                return False
            baseline = self._session_baseline_sha
            if baseline is not None and remote_sha == baseline:
                return False
            return True

    def snapshot(self) -> UpdateStateSnapshot:
        with self._lock:
            result = self._last_check
            available = bool(result and result.behind)
            return UpdateStateSnapshot(
                available=available,
                commits_behind=result.commits_behind if result else None,
                remote_sha=result.remote_sha if result else None,
                local_sha=result.local_sha if result else None,
                branch=result.branch if result else None,
                last_checked_at=(
                    self._last_checked_at.isoformat() if self._last_checked_at is not None else None
                ),
                message=result.message if result else None,
            )

    def reset(self) -> None:
        with self._lock:
            self._session_baseline_sha = None
            self._dismissed_remote_sha = None
            self._last_check = None
            self._last_checked_at = None
            self._prompt_offered_for_sha = None


update_store = UpdateStore()
