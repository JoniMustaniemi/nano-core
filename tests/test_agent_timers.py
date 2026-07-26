from datetime import UTC, datetime, timedelta

from helpers.agent_fixtures import (
    DuplicateTimerClient,
    ShouldNotBeCalledClient,
    agent_respond,
    patch_agent,
)

from app.assistant.pending import pending_interactions
from app.assistant.rules.timers import (
    is_stopwatch_start_request,
    is_stopwatch_stop_request,
    is_timer_cancel_request,
    is_timer_start_request,
    is_timer_status_request,
)
from app.memory import repository
from app.runtime.status_copy import (
    STOPWATCH_STARTED_MESSAGE,
    TIMER_DURATION_PROMPT,
    TIMER_DURATION_RETRY_PROMPT,
)


def test_timer_cancel_ignores_clear_inside_other_words() -> None:
    assert not is_timer_cancel_request("Improve yourself by making timer messages clearer.")
    assert is_timer_cancel_request("Cancel timers.")


def test_timer_start_accepts_add_phrase() -> None:
    assert is_timer_start_request("Add a timer for 30 seconds.")
    assert is_timer_start_request("Can you add timer for 5 minutes?")
    assert is_timer_start_request("Make a new timer for 1 minute.")
    assert not is_timer_start_request("I added timer support yesterday.")


def test_stopwatch_start_and_stop_phrases() -> None:
    assert is_stopwatch_start_request("Start a stopwatch.")
    assert is_stopwatch_start_request("Add stopwatch.")
    assert is_stopwatch_stop_request("Stop stopwatch.")
    assert is_stopwatch_stop_request("Stop stop watch.")
    assert not is_stopwatch_start_request("Stop stopwatch.")


def test_stop_watch_spelling_does_not_trigger_timer_cancel() -> None:
    assert is_timer_status_request("What stop watches are running?")
    assert is_timer_status_request("Status of stop watch.")
    assert not is_timer_status_request("Stop stop watch.")


def test_agent_handles_add_timer_phrase_without_model(monkeypatch, tmp_path) -> None:
    client = DuplicateTimerClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )

    content = agent_respond("Add a timer for 30 seconds.")
    timers = repository.list_timers()

    assert content == "The timer is set for 30 seconds."
    assert client.calls == 0
    assert len(timers) == 1


def test_agent_starts_stopwatch_without_model(monkeypatch, tmp_path) -> None:
    client = DuplicateTimerClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )

    content = agent_respond("Start a stopwatch.")
    stopwatches = repository.list_stopwatches()

    assert content == STOPWATCH_STARTED_MESSAGE
    assert client.calls == 0
    assert len(stopwatches) == 1
    assert stopwatches[0].label == "Stopwatch"


def test_agent_stops_stopwatch_without_model(monkeypatch, tmp_path) -> None:
    client = ShouldNotBeCalledClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )
    repository.add_stopwatch("Lap")

    content = agent_respond("Stop stopwatch.")

    assert content == "Stopped 1 stopwatch."
    assert repository.list_stopwatches() == []


def test_agent_handles_explicit_timer_requests_without_model(monkeypatch, tmp_path) -> None:
    """
    Verify that agent handles explicit timer requests without model.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = DuplicateTimerClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )

    content = agent_respond("Start a timer for 30 seconds.")
    timers = repository.list_timers()

    assert content == "The timer is set for 30 seconds."
    assert client.calls == 0
    assert len(timers) == 1
    assert timers[0].label == "Timer"


def test_agent_lists_active_timers_without_model(monkeypatch, tmp_path) -> None:
    """
    Verify that agent lists active timers without model.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = ShouldNotBeCalledClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )
    repository.add_timer("Tea", datetime.now(UTC) + timedelta(minutes=5))

    content = agent_respond("Check active timers.")

    assert "Tea has" in content
    assert "remaining" in content


def test_agent_cancels_active_timers_without_model(monkeypatch, tmp_path) -> None:
    """
    Verify that agent cancels active timers without model.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = ShouldNotBeCalledClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )
    repository.add_timer("Tea", datetime.now(UTC) + timedelta(minutes=5))

    content = agent_respond("Cancel timers.")

    assert content == "Cancelled 1 timer."
    assert repository.list_timers() == []


def test_agent_cancel_timer_never_starts_timer(monkeypatch, tmp_path) -> None:
    """
    Verify that agent cancel timer never starts timer.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = ShouldNotBeCalledClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )

    content = agent_respond("Cancel timer for two minutes.")

    assert content == "No active timers to cancel."
    assert repository.list_timers() == []


def test_agent_checks_timers_instead_of_completing_pending_timer(monkeypatch, tmp_path) -> None:
    """
    Verify that agent checks timers instead of completing pending timer.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = ShouldNotBeCalledClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )
    repository.add_timer("Tea", datetime.now(UTC) + timedelta(minutes=5))

    first = agent_respond("Start a timer.")
    second = agent_respond("Check active timers.")
    timers = repository.list_timers()

    assert first == TIMER_DURATION_PROMPT
    assert "Tea has" in second
    assert "remaining" in second
    assert len(timers) == 1
    assert timers[0].label == "Tea"


def test_agent_cancels_pending_timer_duration_request(monkeypatch, tmp_path) -> None:
    """
    Verify that agent cancels pending timer duration request.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = ShouldNotBeCalledClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )

    first = agent_respond("Start a timer.")
    second = agent_respond("Cancel timers.")

    assert first == TIMER_DURATION_PROMPT
    assert second == "No active timers to cancel."
    assert pending_interactions.get("default") is None
    assert repository.list_timers() == []


def test_agent_asks_for_timer_duration_before_using_model(monkeypatch, tmp_path) -> None:
    """
    Verify that agent asks for timer duration before using model.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    patch_agent(monkeypatch, client=ShouldNotBeCalledClient(), tmp_path=tmp_path)

    content = agent_respond("Start a timer.")

    assert content == TIMER_DURATION_PROMPT
    assert repository.list_timers() == []


def test_agent_starts_timer_after_duration_follow_up(monkeypatch, tmp_path) -> None:
    """
    Verify that agent starts timer after duration follow up.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    patch_agent(
        monkeypatch,
        client=ShouldNotBeCalledClient(),
        tmp_path=tmp_path,
        announce=lambda text: None,
    )

    first = agent_respond("Start a timer.")
    second = agent_respond("30 seconds")
    timers = repository.list_timers()

    assert first == TIMER_DURATION_PROMPT
    assert second == "The timer is set for 30 seconds."
    assert len(timers) == 1
    assert timers[0].label == "Timer"


def test_agent_starts_timer_after_spoken_duration_follow_up(monkeypatch, tmp_path) -> None:
    """
    Verify that agent starts timer after spoken duration follow up.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    patch_agent(
        monkeypatch,
        client=ShouldNotBeCalledClient(),
        tmp_path=tmp_path,
        announce=lambda text: None,
    )

    first = agent_respond("Start a timer.")
    second = agent_respond("five minutes")
    timers = repository.list_timers()

    assert first == TIMER_DURATION_PROMPT
    assert second == "The timer is set for 5 minutes."
    assert len(timers) == 1
    assert timers[0].label == "Timer"


def test_agent_cancels_pending_timer_with_never_mind(monkeypatch, tmp_path) -> None:
    patch_agent(
        monkeypatch,
        client=ShouldNotBeCalledClient(),
        tmp_path=tmp_path,
        announce=lambda text: None,
    )

    first = agent_respond("Start a timer.")
    second = agent_respond("Never mind.")

    assert first == TIMER_DURATION_PROMPT
    assert second == "Timer cancelled."
    assert pending_interactions.get("default") is None
    assert repository.list_timers() == []


def test_agent_retries_after_invalid_timer_duration_follow_up(monkeypatch, tmp_path) -> None:
    patch_agent(
        monkeypatch,
        client=ShouldNotBeCalledClient(),
        tmp_path=tmp_path,
        announce=lambda text: None,
    )

    first = agent_respond("Start a timer.")
    second = agent_respond("soon")

    assert first == TIMER_DURATION_PROMPT
    assert second == TIMER_DURATION_RETRY_PROMPT
    assert pending_interactions.get("default") is not None
    assert repository.list_timers() == []


def test_agent_starts_timer_after_bare_number_duration_follow_up(monkeypatch, tmp_path) -> None:
    patch_agent(
        monkeypatch,
        client=ShouldNotBeCalledClient(),
        tmp_path=tmp_path,
        announce=lambda text: None,
    )

    first = agent_respond("Start a timer.")
    second = agent_respond("10")
    timers = repository.list_timers()

    assert first == TIMER_DURATION_PROMPT
    assert second == "The timer is set for 10 minutes."
    assert len(timers) == 1


def test_agent_handles_non_example_timer_duration_without_model(monkeypatch, tmp_path) -> None:
    patch_agent(
        monkeypatch,
        client=ShouldNotBeCalledClient(),
        tmp_path=tmp_path,
        announce=lambda text: None,
    )

    content = agent_respond("Start a timer for 45 seconds.")
    timers = repository.list_timers()

    assert content == "The timer is set for 45 seconds."
    assert len(timers) == 1


def test_agent_understands_spoken_timer_duration_in_single_request(monkeypatch, tmp_path) -> None:
    patch_agent(
        monkeypatch,
        client=ShouldNotBeCalledClient(),
        tmp_path=tmp_path,
        announce=lambda text: None,
    )

    content = agent_respond("Start a timer for five minutes.")
    timers = repository.list_timers()

    assert content == "The timer is set for 5 minutes."
    assert len(timers) == 1
    assert timers[0].label == "Timer"
