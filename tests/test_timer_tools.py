from datetime import UTC, datetime, timedelta

import pytest
from helpers.voice_announce import patch_announce_voice

from app.memory import repository
from app.runtime.activity import activity
from app.scheduler.jobs import (
    _format_due_timer,
    _timer_job_id,
    check_due_timers,
    schedule_timer,
    scheduler,
)
from app.tools import get_tool
from app.tools.errors import ToolError


@pytest.fixture(autouse=True)
def clear_scheduled_timer_jobs() -> None:
    def _clear() -> None:
        for job in list(scheduler.get_jobs()):
            if job.id.startswith("timer:"):
                scheduler.remove_job(job.id)

    _clear()
    yield
    _clear()


def test_start_timer_accepts_duration_text() -> None:
    """
    Verify that start timer accepts duration text.

    Returns:
        None.
    """
    tool = get_tool("start_timer")

    assert tool is not None
    result = tool.handler({"duration_text": "2min", "label": "Tea"})
    timers = repository.list_timers()

    assert "started timer" in result
    assert timers[0].label == "Tea"


def test_start_timer_accepts_spoken_duration_text() -> None:
    """
    Verify that start timer accepts spoken duration text.

    Returns:
        None.
    """
    tool = get_tool("start_timer")

    assert tool is not None
    result = tool.handler({"duration_text": "five minutes", "label": "Tea"})
    timers = repository.list_timers()

    assert "started timer" in result
    assert timers[0].label == "Tea"


def test_start_timer_requires_explicit_duration() -> None:
    """
    Verify that start timer requires explicit duration.

    Returns:
        None.
    """
    tool = get_tool("start_timer")

    assert tool is not None
    with pytest.raises(ToolError, match="Timer duration is required"):
        tool.handler({"label": "Tea"})
    timers = repository.list_timers()

    assert timers == []


def test_list_timers_reports_time_remaining() -> None:
    """
    Verify that list timers reports time remaining.

    Returns:
        None.
    """
    tool = get_tool("list_timers")
    repository.add_timer("Timer", datetime.now(UTC) + timedelta(minutes=5))

    assert tool is not None
    result = tool.handler({})

    assert result.startswith("You have one timer active.")
    assert "remaining" in result


def test_list_timers_reports_multiple_timers_with_count() -> None:
    """
    Verify that list timers reports multiple timers with count.

    Returns:
        None.
    """
    tool = get_tool("list_timers")
    repository.add_timer("Tea", datetime.now(UTC) + timedelta(minutes=5))
    repository.add_timer("Laundry", datetime.now(UTC) + timedelta(minutes=10))

    assert tool is not None
    result = tool.handler({})

    assert result.startswith("You have 2 timers active:")
    assert "Tea has" in result
    assert "Laundry has" in result
    assert "1:" not in result
    assert "2:" not in result


def test_cancel_timers_removes_all_active_timers() -> None:
    """
    Verify that cancel timers removes active timers.

    Returns:
        None.
    """
    tool = get_tool("cancel_timers")
    repository.add_timer("Tea", datetime.now(UTC) + timedelta(minutes=5))
    repository.add_timer("Laundry", datetime.now(UTC) + timedelta(minutes=10))

    assert tool is not None
    result = tool.handler({})
    timers = repository.list_timers()

    assert result == "Cancelled 2 timers: Tea, Laundry."
    assert timers == []


def test_cancel_timers_reports_when_none_are_active() -> None:
    """
    Verify that cancel timers reports when none are active.

    Returns:
        None.
    """
    tool = get_tool("cancel_timers")

    assert tool is not None
    result = tool.handler({})

    assert result == "No active timers to cancel."


def test_due_timer_logs_friendly_completion_message() -> None:
    """
    Verify that due timer logs friendly completion message.

    Returns:
        None.
    """
    repository.add_timer("Tea", datetime.now(UTC) - timedelta(minutes=2))

    check_due_timers()
    snapshot = activity.snapshot()
    events = snapshot["events"]
    timers = repository.list_timers()

    assert any(event["title"] == "Timer complete." for event in events)
    assert any("timer for Tea is complete." in str(event["detail"]) for event in events)
    assert timers == []


def test_due_timer_announces_completion(monkeypatch) -> None:
    """
    Verify that due timer announces completion.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.
    """
    spoken: list[str] = []
    repository.add_timer("Tea", datetime.now(UTC) - timedelta(seconds=10))
    patch_announce_voice(monkeypatch, spoken)

    check_due_timers()

    assert spoken
    assert "timer for Tea is complete." in spoken[0]


def test_due_default_timer_omits_default_label() -> None:
    """
    Verify that due default timer omits default label.

    Returns:
        None.
    """
    _, detail = _format_due_timer(
        "Timer",
        datetime.now(UTC) - timedelta(seconds=30),
        datetime.now(UTC),
    )

    assert detail == "Your 30 seconds timer is complete."


def test_due_one_hour_timer_uses_hour_phrasing() -> None:
    _, detail = _format_due_timer(
        "Tea",
        datetime.now(UTC) - timedelta(hours=1),
        datetime.now(UTC),
    )

    assert detail == "Your 1 hour timer for Tea is complete."


def test_start_timer_schedules_completion_job() -> None:
    tool = get_tool("start_timer")
    assert tool is not None

    tool.handler({"duration_seconds": 45, "label": "Tea"})

    timers = repository.list_timers()
    assert len(timers) == 1
    timer = timers[0]
    assert timer.id is not None

    job = scheduler.get_job(_timer_job_id(timer.id))
    assert job is not None
    assert job.args == (timer.id,)


def test_cancel_timers_unschedules_completion_job() -> None:
    due_at = datetime.now(UTC) + timedelta(minutes=5)
    timer = repository.add_timer("Tea", due_at)
    assert timer.id is not None
    schedule_timer(timer.id, due_at)
    assert scheduler.get_job(_timer_job_id(timer.id)) is not None

    tool = get_tool("cancel_timers")
    assert tool is not None
    tool.handler({})

    assert repository.list_timers() == []
    assert scheduler.get_job(_timer_job_id(timer.id)) is None


def test_schedule_timer_uses_due_at_as_run_date() -> None:
    due_at = datetime.now(UTC) + timedelta(seconds=30)
    timer = repository.add_timer("Tea", due_at)
    assert timer.id is not None

    schedule_timer(timer.id, timer.due_at)
    job = scheduler.get_job(_timer_job_id(timer.id))
    assert job is not None
    run_date = job.trigger.run_date
    if run_date.tzinfo is None:
        run_date = run_date.replace(tzinfo=UTC)
    timer_due_at = timer.due_at
    if timer_due_at.tzinfo is None:
        timer_due_at = timer_due_at.replace(tzinfo=UTC)
    assert abs((run_date - timer_due_at).total_seconds()) < 1


def test_start_stopwatch_creates_running_stopwatch() -> None:
    tool = get_tool("start_stopwatch")
    assert tool is not None

    result = tool.handler({})

    assert result == "Stopwatch started."
    stopwatches = repository.list_stopwatches()
    assert len(stopwatches) == 1
    assert stopwatches[0].label == "Stopwatch"


def test_stop_stopwatches_removes_active_stopwatch() -> None:
    repository.add_stopwatch("Lap")
    tool = get_tool("stop_stopwatches")
    assert tool is not None

    result = tool.handler({})

    assert result == "Stopped 1 stopwatch."
    assert repository.list_stopwatches() == []


def test_clear_all_timers_removes_countdowns_and_stopwatches() -> None:
    due_at = datetime.now(UTC) + timedelta(minutes=5)
    timer = repository.add_timer("Tea", due_at)
    repository.add_stopwatch("Lap")
    assert timer.id is not None
    schedule_timer(timer.id, due_at)

    tool = get_tool("clear_all_timers")
    assert tool is not None

    result = tool.handler({})

    assert result == "Cleared 1 countdown timer and 1 stopwatch."
    assert repository.list_timers() == []
    assert scheduler.get_job(_timer_job_id(timer.id)) is None


def test_clear_all_timers_reports_when_none_are_active() -> None:
    tool = get_tool("clear_all_timers")
    assert tool is not None

    result = tool.handler({})

    assert result == "No active timers."


def test_list_timers_reports_stopwatch_elapsed() -> None:
    repository.add_stopwatch("Lap", started_at=datetime.now(UTC) - timedelta(minutes=2))
    tool = get_tool("list_timers")
    assert tool is not None

    result = tool.handler({})

    assert "stopwatch has been running for" in result


def test_sync_timer_schedules_skips_stopwatches() -> None:
    from app.scheduler.jobs import _timer_job_id, scheduler, sync_timer_schedules

    countdown = repository.add_timer("Tea", datetime.now(UTC) + timedelta(minutes=5))
    stopwatch = repository.add_stopwatch("Lap")
    assert countdown.id is not None
    assert stopwatch.id is not None

    sync_timer_schedules()

    assert scheduler.get_job(_timer_job_id(countdown.id)) is not None
    assert scheduler.get_job(_timer_job_id(stopwatch.id)) is None


def test_rename_timer_by_id_when_labels_duplicate() -> None:
    due_at = datetime.now(UTC) + timedelta(minutes=5)
    first = repository.add_timer("Timer", due_at)
    second = repository.add_timer("Timer", due_at + timedelta(minutes=1))
    assert first.id is not None
    assert second.id is not None

    tool = get_tool("rename_timer")
    assert tool is not None
    result = tool.handler({"timer_id": first.id, "new_label": "Pizza"})

    timers = repository.list_countdown_timers()
    by_id = {timer.id: timer for timer in timers}
    assert result == 'Renamed timer to "Pizza".'
    assert by_id[first.id].label == "Pizza"
    assert by_id[second.id].label == "Timer"
    assert by_id[first.id].due_at == first.due_at
    assert by_id[first.id].created_at == first.created_at


def test_rename_timer_by_unique_label() -> None:
    due_at = datetime.now(UTC) + timedelta(minutes=5)
    timer = repository.add_timer("Tea", due_at)
    assert timer.id is not None

    tool = get_tool("rename_timer")
    assert tool is not None
    result = tool.handler({"label": "Tea", "new_label": "Coffee"})

    updated = repository.get_timer(timer.id)
    assert updated is not None
    assert result == 'Renamed timer to "Coffee".'
    assert updated.label == "Coffee"
    assert updated.due_at == timer.due_at


def test_rename_timer_rejects_ambiguous_label() -> None:
    due_at = datetime.now(UTC) + timedelta(minutes=5)
    repository.add_timer("Timer", due_at)
    repository.add_timer("Timer", due_at + timedelta(minutes=1))

    tool = get_tool("rename_timer")
    assert tool is not None
    with pytest.raises(ToolError, match="Multiple timers labeled"):
        tool.handler({"label": "Timer", "new_label": "Pizza"})


def test_rename_timer_requires_target() -> None:
    repository.add_timer("Tea", datetime.now(UTC) + timedelta(minutes=5))
    tool = get_tool("rename_timer")
    assert tool is not None

    with pytest.raises(ToolError, match="Specify which timer to rename"):
        tool.handler({"new_label": "Pizza"})


def test_rename_timer_rejects_invalid_label() -> None:
    timer = repository.add_timer("Tea", datetime.now(UTC) + timedelta(minutes=5))
    tool = get_tool("rename_timer")
    assert tool is not None

    with pytest.raises(ToolError, match="at most 64 characters"):
        tool.handler({"timer_id": timer.id, "new_label": "x" * 65})

    with pytest.raises(ToolError, match="control characters"):
        tool.handler({"timer_id": timer.id, "new_label": "Bad\x00Label"})


def test_rename_timer_allows_cancel_by_new_label() -> None:
    timer = repository.add_timer("Tea", datetime.now(UTC) + timedelta(minutes=5))
    rename_tool = get_tool("rename_timer")
    cancel_tool = get_tool("cancel_timers")
    assert rename_tool is not None
    assert cancel_tool is not None

    rename_tool.handler({"timer_id": timer.id, "new_label": "Coffee"})
    assert cancel_tool.handler({"label": "Tea"}) == "No matching active timers to cancel."
    assert cancel_tool.handler({"label": "Coffee"}) == "Cancelled 1 timer."


def test_rename_stopwatch_by_id_preserves_started_at() -> None:
    started_at = datetime.now(UTC) - timedelta(seconds=30)
    stopwatch = repository.add_stopwatch("Lap", started_at=started_at)
    assert stopwatch.id is not None

    tool = get_tool("rename_stopwatch")
    assert tool is not None
    result = tool.handler({"stopwatch_id": stopwatch.id, "new_label": "Run"})

    updated = repository.get_timer(stopwatch.id)
    assert updated is not None
    assert result == 'Renamed stopwatch to "Run".'
    assert updated.label == "Run"
    updated_started_at = updated.created_at
    if updated_started_at.tzinfo is None:
        updated_started_at = updated_started_at.replace(tzinfo=UTC)
    assert updated_started_at == started_at
