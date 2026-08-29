from datetime import UTC, datetime, timedelta

from helpers.agent_fixtures import (
    DuplicateTimerClient,
    ShouldNotBeCalledClient,
    agent_respond,
    patch_agent,
)

from app.assistant.pending import pending_interactions
from app.assistant.rules.timers import (
    is_clear_all_timers_request,
    is_stopwatch_rename_request,
    is_stopwatch_start_request,
    is_stopwatch_stop_request,
    is_timer_cancel_request,
    is_timer_rename_request,
    is_timer_start_request,
    is_timer_status_request,
    parse_stopwatch_stop_args,
    parse_timer_cancel_args,
    rename_timer_args_from_message,
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


def test_clear_all_timers_phrases() -> None:
    assert is_clear_all_timers_request("Clear all timers.")
    assert is_clear_all_timers_request("Delete all timers.")
    assert is_clear_all_timers_request("Stop all timers.")
    assert not is_clear_all_timers_request("Cancel timers.")
    assert not is_clear_all_timers_request("Stop stopwatch.")


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


def test_agent_clears_all_timers_without_model(monkeypatch, tmp_path) -> None:
    client = ShouldNotBeCalledClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )
    repository.add_timer("Tea", datetime.now(UTC) + timedelta(minutes=5))
    repository.add_stopwatch("Lap")

    content = agent_respond("Clear all timers.")

    assert content == "Cleared 1 countdown timer and 1 stopwatch."
    assert repository.list_timers() == []


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


def test_timer_rename_phrases() -> None:
    assert is_timer_rename_request('Rename timer 3 to "Pizza"')
    assert is_timer_rename_request('Rename the timer "Tea" to "Coffee"')
    assert not is_timer_rename_request("Cancel timers.")
    assert not is_timer_rename_request('Rename stopwatch 2 to "Run"')


def test_stopwatch_rename_phrases() -> None:
    assert is_stopwatch_rename_request('Rename stopwatch 2 to "Run"')
    assert is_stopwatch_rename_request('Rename the stopwatch "Lap" to "Run"')
    assert not is_stopwatch_rename_request("Stop stopwatch.")


def test_rename_timer_args_from_message() -> None:
    assert rename_timer_args_from_message('Rename timer 3 to "Pizza"') == {
        "timer_id": 3,
        "new_label": "Pizza",
    }
    assert rename_timer_args_from_message('Rename the timer "Tea" to "Coffee"') == {
        "label": "Tea",
        "new_label": "Coffee",
    }
    assert rename_timer_args_from_message("Rename timer 5 to Pizza") == {
        "timer_id": 5,
        "new_label": "Pizza",
    }


def test_agent_renames_timer_by_id_without_model(monkeypatch, tmp_path) -> None:
    client = ShouldNotBeCalledClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )
    timer = repository.add_timer("Timer", datetime.now(UTC) + timedelta(minutes=5))
    assert timer.id is not None

    content = agent_respond(f'Rename timer {timer.id} to "Pizza"')
    updated = repository.get_timer(timer.id)

    assert content == ""
    assert updated is not None
    assert updated.label == "Pizza"


def test_timer_rename_phrases_reject_broad_matches() -> None:
    assert not is_timer_rename_request("Rename timer please.")
    assert not is_timer_rename_request('Rename stopwatch 2 to "Run"')


def test_timer_rename_accepts_trailing_period_and_smart_quotes() -> None:
    assert is_timer_rename_request("Rename timer 3 to “Pizza”.")
    assert rename_timer_args_from_message("Rename timer 3 to “Pizza”.") == {
        "timer_id": 3,
        "new_label": "Pizza",
    }


def test_agent_renames_stopwatch_by_label_without_model(monkeypatch, tmp_path) -> None:
    client = ShouldNotBeCalledClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )
    stopwatch = repository.add_stopwatch("Lap")
    assert stopwatch.id is not None

    content = agent_respond('Rename the stopwatch "Lap" to "Run"')
    updated = repository.get_timer(stopwatch.id)

    assert content == ""
    assert updated is not None
    assert updated.label == "Run"


def test_agent_reports_ambiguous_timer_rename_without_model(monkeypatch, tmp_path) -> None:
    from app.assistant.agent_router import AgentRouter

    due_at = datetime.now(UTC) + timedelta(minutes=5)
    repository.add_timer("Timer", due_at)
    repository.add_timer("Timer", due_at + timedelta(minutes=1))

    decision = AgentRouter().decide(
        'Rename the timer "Timer" to "Pizza"',
        conversation_id="default",
        history=[],
    )

    assert decision.mode == "tool"
    assert decision.tool_name == "rename_timer"
    assert decision.tool_args == {"label": "Timer", "new_label": "Pizza"}


def test_parse_timer_cancel_args_matches_id_phrase() -> None:
    assert parse_timer_cancel_args("Cancel timer 2") == {"timer_id": 2}
    assert parse_timer_cancel_args("Cancel timer 2.") == {"timer_id": 2}
    assert parse_timer_cancel_args("Cancel timers.") is None


def test_agent_router_routes_cancel_timer_by_id(monkeypatch, tmp_path) -> None:
    from app.assistant.agent_router import AgentRouter

    due_at = datetime.now(UTC) + timedelta(minutes=5)
    timer = repository.add_timer("Tea", due_at)
    assert timer.id is not None

    decision = AgentRouter().decide(
        f"Cancel timer {timer.id}",
        conversation_id="default",
        history=[],
    )

    assert decision.mode == "tool"
    assert decision.tool_name == "cancel_timers"
    assert decision.tool_args == {"timer_id": timer.id}


def test_agent_cancels_only_requested_timer_with_multiple_active(monkeypatch, tmp_path) -> None:
    client = ShouldNotBeCalledClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )
    due_at = datetime.now(UTC) + timedelta(minutes=5)
    timer_one = repository.add_timer("One", due_at)
    timer_two = repository.add_timer("Two", due_at + timedelta(minutes=1))
    timer_three = repository.add_timer("Three", due_at + timedelta(minutes=2))
    assert timer_one.id is not None
    assert timer_two.id is not None
    assert timer_three.id is not None

    content = agent_respond(f"Cancel timer {timer_two.id}")
    remaining_ids = [timer.id for timer in repository.list_timers()]

    assert content == ""
    assert remaining_ids == [timer_one.id, timer_three.id]


def test_agent_singular_cancel_with_multiple_timers_returns_clarification(
    monkeypatch,
    tmp_path,
) -> None:
    client = ShouldNotBeCalledClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )
    due_at = datetime.now(UTC) + timedelta(minutes=5)
    repository.add_timer("One", due_at)
    repository.add_timer("Two", due_at + timedelta(minutes=1))

    content = agent_respond("Cancel the timer.")

    assert "Multiple timers are running" in content
    assert len(repository.list_timers()) == 2


def test_agent_singular_cancel_with_one_timer_cancels_it(monkeypatch, tmp_path) -> None:
    client = ShouldNotBeCalledClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )
    repository.add_timer("Tea", datetime.now(UTC) + timedelta(minutes=5))

    content = agent_respond("Cancel the timer.")

    assert content == "Cancelled 1 timer."
    assert repository.list_timers() == []


def test_parse_stopwatch_stop_args_matches_id_phrase() -> None:
    assert parse_stopwatch_stop_args("Stop stopwatch 2") == {"stopwatch_id": 2}
    assert parse_stopwatch_stop_args("Stop stopwatch 2.") == {"stopwatch_id": 2}
    assert parse_stopwatch_stop_args("Stop stop watch 2.") == {"stopwatch_id": 2}
    assert parse_stopwatch_stop_args("Stop stopwatches.") is None


def test_agent_router_routes_stop_stopwatch_by_id(monkeypatch, tmp_path) -> None:
    from app.assistant.agent_router import AgentRouter

    stopwatch = repository.add_stopwatch("Lap")
    assert stopwatch.id is not None

    decision = AgentRouter().decide(
        f"Stop stopwatch {stopwatch.id}",
        conversation_id="default",
        history=[],
    )

    assert decision.mode == "tool"
    assert decision.tool_name == "stop_stopwatches"
    assert decision.tool_args == {"stopwatch_id": stopwatch.id}


def test_agent_stops_only_requested_stopwatch_with_multiple_active(monkeypatch, tmp_path) -> None:
    client = ShouldNotBeCalledClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )
    stopwatch_one = repository.add_stopwatch("One")
    stopwatch_two = repository.add_stopwatch("Two")
    stopwatch_three = repository.add_stopwatch("Three")
    assert stopwatch_one.id is not None
    assert stopwatch_two.id is not None
    assert stopwatch_three.id is not None

    content = agent_respond(f"Stop stopwatch {stopwatch_two.id}")
    remaining_ids = [stopwatch.id for stopwatch in repository.list_stopwatches()]

    assert content == ""
    assert remaining_ids == [stopwatch_one.id, stopwatch_three.id]


def test_agent_singular_stopwatch_with_multiple_active_returns_clarification(
    monkeypatch,
    tmp_path,
) -> None:
    client = ShouldNotBeCalledClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )
    repository.add_stopwatch("One")
    repository.add_stopwatch("Two")

    content = agent_respond("Stop the stopwatch.")

    assert "Multiple stopwatches are running" in content
    assert len(repository.list_stopwatches()) == 2


def test_agent_singular_stopwatch_with_one_active_stops_it(monkeypatch, tmp_path) -> None:
    client = ShouldNotBeCalledClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )
    repository.add_stopwatch("Lap")

    content = agent_respond("Stop the stopwatch.")

    assert content == "Stopped 1 stopwatch."
    assert repository.list_stopwatches() == []
