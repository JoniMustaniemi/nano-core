from datetime import UTC, datetime, timedelta

import pytest

from app.memory import repository
from app.runtime.activity import activity
from app.scheduler.jobs import _format_due_timer, check_due_timers
from app.tools import get_tool
from app.tools.errors import ToolError


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

    assert result.startswith("You have one timer active and it has")
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
    monkeypatch.setattr(
        "app.scheduler.jobs.GladosVoiceService.announce",
        lambda self, text: spoken.append(text),
    )

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
