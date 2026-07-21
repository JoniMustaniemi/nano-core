from datetime import UTC, datetime, timedelta

from helpers.agent_fixtures import (
    DuplicateTimerClient,
    ShouldNotBeCalledClient,
    patch_agent,
)

from app.assistant.agent import AgentService
from app.assistant.pending import pending_interactions
from app.memory import repository


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
        announce=lambda self, text: None,
    )

    content = AgentService().respond("Start a timer for 30 seconds.")
    reminders = repository.list_reminders()

    assert content == "The timer is set for 30 seconds."
    assert client.calls == 0
    assert len(reminders) == 1
    assert reminders[0].content == "[timer] Timer"



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
        announce=lambda self, text: None,
    )
    repository.add_reminder("[timer] Tea", datetime.now(UTC) + timedelta(minutes=5))

    content = AgentService().respond("Check active timers.")

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
        announce=lambda self, text: None,
    )
    repository.add_reminder("[timer] Tea", datetime.now(UTC) + timedelta(minutes=5))

    content = AgentService().respond("Cancel timers.")

    assert content == "Cancelled 1 timer."
    assert repository.list_reminders() == []



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
        announce=lambda self, text: None,
    )

    content = AgentService().respond("Cancel timer for two minutes.")

    assert content == "No active timers to cancel."
    assert repository.list_reminders() == []



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
        announce=lambda self, text: None,
    )
    repository.add_reminder("[timer] Tea", datetime.now(UTC) + timedelta(minutes=5))

    first = AgentService().respond("Start a timer.")
    second = AgentService().respond("Check active timers.")
    reminders = repository.list_reminders()

    assert first == "How long should the timer run?"
    assert "Tea has" in second
    assert "remaining" in second
    assert len(reminders) == 1
    assert reminders[0].content == "[timer] Tea"



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
        announce=lambda self, text: None,
    )

    first = AgentService().respond("Start a timer.")
    second = AgentService().respond("Cancel timers.")

    assert first == "How long should the timer run?"
    assert second == "No active timers to cancel."
    assert pending_interactions.get("default") is None
    assert repository.list_reminders() == []



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

    content = AgentService().respond("Start a timer.")

    assert content == "How long should the timer run?"
    assert repository.list_reminders() == []



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
        announce=lambda self, text: None,
    )

    first = AgentService().respond("Start a timer.")
    second = AgentService().respond("30 seconds")
    reminders = repository.list_reminders()

    assert first == "How long should the timer run?"
    assert second == "The timer is set for 30 seconds."
    assert len(reminders) == 1
    assert reminders[0].content == "[timer] Timer"



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
        announce=lambda self, text: None,
    )

    first = AgentService().respond("Start a timer.")
    second = AgentService().respond("five minutes")
    reminders = repository.list_reminders()

    assert first == "How long should the timer run?"
    assert second == "The timer is set for 5 minutes."
    assert len(reminders) == 1
    assert reminders[0].content == "[timer] Timer"



def test_agent_understands_spoken_timer_duration_in_single_request(monkeypatch, tmp_path) -> None:
    """
    Verify that agent understands spoken timer duration in single request.

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
        announce=lambda self, text: None,
    )

    content = AgentService().respond("Start a timer for five minutes.")
    reminders = repository.list_reminders()

    assert content == "The timer is set for 5 minutes."
    assert len(reminders) == 1
    assert reminders[0].content == "[timer] Timer"


