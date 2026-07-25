from app.runtime.long_task_progress import (
    LongTaskProgress,
    LongTaskProgressReporter,
    format_progress_update,
)


def test_format_progress_update_for_plan_step() -> None:
    announcement = format_progress_update(
        LongTaskProgress(
            task_name="self-improvement",
            step="plan",
            current_file="app/assistant/rules/messages.py",
            file_index=1,
            file_count=1,
            attempt=2,
        )
    )

    assert announcement.title == "Still improving myself."
    assert "messages.py" in (announcement.detail or "")
    assert "message helpers" in announcement.spoken
    assert "attempt two" in announcement.spoken


def test_format_progress_update_for_pr_verify_step() -> None:
    announcement = format_progress_update(
        LongTaskProgress(
            task_name="pull request",
            step="verify",
        )
    )

    assert announcement.title == "I'm verifying the project."
    assert "few minutes" in (announcement.detail or "")
    assert "verifying the project" in announcement.spoken.lower()


def test_progress_reporter_emits_activity_log() -> None:
    logged: list[dict[str, str | None]] = []
    reporter = LongTaskProgressReporter(
        task_name="self-improvement",
        goal="clearer messages",
        log_fn=lambda **kwargs: logged.append(kwargs),
        time_fn=lambda: 0.0,
        sleep_fn=lambda _seconds: None,
    )
    reporter.update(step="select")
    reporter._announce()

    assert logged
    assert logged[0]["source"] == "runtime.long_task_progress"
    assert "choosing which files" in (logged[0]["detail"] or "").lower()


def test_progress_reporter_emits_activity_log_on_interval() -> None:
    logged: list[dict[str, str | None]] = []
    clock = {"now": 0.0}

    reporter = LongTaskProgressReporter(
        task_name="self-improvement",
        goal="clearer messages",
        interval_seconds=120,
        log_fn=lambda **kwargs: logged.append(kwargs),
        time_fn=lambda: clock["now"],
        sleep_fn=lambda _seconds: None,
    )
    reporter.update(step="select")
    reporter._last_announced_at = 0.0
    clock["now"] = 121.0
    reporter._announce()

    assert logged
    assert logged[-1]["source"] == "runtime.long_task_progress"


def test_progress_reporter_can_announce_on_start() -> None:
    logged: list[dict[str, str | None]] = []

    with LongTaskProgressReporter(
        task_name="pull request",
        interval_seconds=120,
        announce_on_start=True,
        log_fn=lambda **kwargs: logged.append(kwargs),
        time_fn=lambda: 0.0,
        sleep_fn=lambda _seconds: None,
    ) as reporter:
        reporter.update(step="verify")

    assert logged
    assert "verifying the project" in (logged[0]["title"] or "").lower()


def test_progress_reporter_stops_thread_on_exit() -> None:
    with LongTaskProgressReporter(
        task_name="self-improvement",
        interval_seconds=120,
        log_fn=lambda **kwargs: None,
        time_fn=lambda: 0.0,
        sleep_fn=lambda _seconds: None,
    ) as reporter:
        thread = reporter._thread
        assert thread is not None
        assert thread.is_alive()

    assert thread is not None
    assert not thread.is_alive()
