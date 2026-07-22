from __future__ import annotations

from datetime import UTC, datetime
from threading import RLock


class UserActivityTracker:
  """Track when the user last interacted with Nano."""

  def __init__(self) -> None:
    self._lock = RLock()
    self._last_activity_at = datetime.now(UTC)

  def touch(self) -> None:
    """Record user activity at the current time."""
    with self._lock:
      self._last_activity_at = datetime.now(UTC)

  def last_activity_at(self) -> datetime:
    """Return the timestamp of the last recorded user activity."""
    with self._lock:
      return self._last_activity_at

  def seconds_idle(self, *, now: datetime | None = None) -> float:
    """Return seconds since the last user activity."""
    current = now or datetime.now(UTC)
    with self._lock:
      return max(0.0, (current - self._last_activity_at).total_seconds())

  def is_idle(self, threshold_seconds: float, *, now: datetime | None = None) -> bool:
    """Return whether the user has been idle for at least threshold_seconds."""
    return self.seconds_idle(now=now) >= threshold_seconds


user_activity = UserActivityTracker()
