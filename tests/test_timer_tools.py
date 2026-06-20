from datetime import UTC, datetime, timedelta

from app.memory import repository
from app.runtime.activity import activity
from app.scheduler.jobs import check_due_reminders
from app.tools import get_tool


def test_start_timer_accepts_duration_text() -> None:
    tool = get_tool("start_timer")

    assert tool is not None
    result = tool.handler({"duration_text": "2min", "label": "Tea"})
    reminders = repository.list_reminders()

    assert "started timer" in result
    assert reminders[0].content == "[timer] Tea"


def test_due_timer_logs_friendly_completion_message() -> None:
    repository.add_reminder("[timer] Tea", datetime.now(UTC) - timedelta(minutes=2))

    check_due_reminders()
    snapshot = activity.snapshot()
    events = snapshot["events"]

    assert any(event["title"] == "Timer complete." for event in events)
    assert any("timer for Tea is complete." in str(event["detail"]) for event in events)
