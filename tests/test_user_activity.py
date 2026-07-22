from datetime import UTC, datetime, timedelta

from app.runtime.user_activity import UserActivityTracker


def test_touch_and_idle() -> None:
    tracker = UserActivityTracker()
    past = datetime.now(UTC) - timedelta(seconds=120)
    tracker._last_activity_at = past
    assert tracker.is_idle(60)
    assert tracker.seconds_idle() >= 60
    tracker.touch()
    assert not tracker.is_idle(60)
