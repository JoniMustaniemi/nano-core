from __future__ import annotations

from datetime import UTC, datetime, timedelta

# Raspberry Pi may boot with the clock at Unix epoch before NTP sync.
MIN_VALID_TIMER_START = datetime(2020, 1, 1, tzinfo=UTC)
_MAX_FUTURE_START = timedelta(minutes=5)


def normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def is_plausible_timer_start(value: datetime) -> bool:
    return normalize_utc(value) >= MIN_VALID_TIMER_START


def resolve_stopwatch_started_at(value: datetime, *, now: datetime | None = None) -> datetime:
    """Map corrupt or missing wall-clock starts to a safe value for API output."""
    current = normalize_utc(now or datetime.now(UTC))
    started = normalize_utc(value)
    if started < MIN_VALID_TIMER_START:
        return current
    if started > current + _MAX_FUTURE_START:
        return current
    return started


def resolve_timer_start_time(started_at: datetime | None) -> datetime:
    """Pick a persisted start time; fail when neither client nor system clock is usable."""
    if started_at is not None:
        candidate = normalize_utc(started_at)
        if is_plausible_timer_start(candidate):
            return candidate
    now = datetime.now(UTC)
    if is_plausible_timer_start(now):
        return now
    raise ValueError("System clock is not set. Wait for network time sync and try again.")
