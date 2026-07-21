from types import SimpleNamespace

from app.assistant.agent import AgentService
from helpers.agent_fixtures import (
    HealthSummaryClient,
    StatusAnswerClient,
    StoryClient,
    patch_agent,
)


def test_agent_can_check_its_own_health(monkeypatch, tmp_path) -> None:
    """
    Verify that agent can check its own health.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = HealthSummaryClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )
    monkeypatch.setattr(
        "app.tools.health_tools.run_health_checks",
        lambda: [
            SimpleNamespace(name="database", ok=True, detail="Database is reachable."),
            SimpleNamespace(name="voice", ok=False, detail="Voice backend is unavailable."),
        ],
    )

    content = AgentService().respond("Check your health.")

    assert content == "My voice check is failing: Voice backend is unavailable."
    assert client.calls == 0



def test_agent_health_summary_is_deterministic_all_clear(monkeypatch, tmp_path) -> None:
    """
    Verify that all-clear health summaries do not depend on model wording.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = HealthSummaryClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )
    monkeypatch.setattr(
        "app.tools.health_tools.run_health_checks",
        lambda: [
            SimpleNamespace(name="database", ok=True, detail="Database is reachable."),
        ],
    )

    content = AgentService().respond("Check your health.")

    assert content == "My diagnostics are clear. No issues were found."
    assert client.calls == 0



def test_agent_health_summary_never_thanks_or_mentions_user_health(
    monkeypatch,
    tmp_path,
) -> None:
    """
    Verify that health diagnostics are about Nano, not the user.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = HealthSummaryClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )
    monkeypatch.setattr(
        "app.tools.health_tools.run_health_checks",
        lambda: [
            SimpleNamespace(name="database", ok=True, detail="Database is reachable."),
        ],
    )

    content = AgentService().respond("Run diagnostics.")

    assert "My diagnostics" in content
    assert "your health" not in content.lower()
    assert "thank" not in content.lower()
    assert client.calls == 0



def test_agent_health_summary_names_failing_check(monkeypatch, tmp_path) -> None:
    """
    Verify that failing health summaries name the failing check and detail.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = HealthSummaryClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )
    monkeypatch.setattr(
        "app.tools.health_tools.run_health_checks",
        lambda: [
            SimpleNamespace(name="database", ok=True, detail="Database is reachable."),
            SimpleNamespace(name="test_failure", ok=False, detail="Testing the warning path."),
        ],
    )

    content = AgentService().respond("Check your health.")

    assert content == "My test_failure check is failing: Testing the warning path."
    assert client.calls == 0



def test_agent_health_summary_handles_missing_failure_detail(monkeypatch, tmp_path) -> None:
    """
    Verify that failing health summaries work without a detail string.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = HealthSummaryClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )
    monkeypatch.setattr(
        "app.tools.health_tools.run_health_checks",
        lambda: [
            SimpleNamespace(name="voice", ok=False, detail=""),
        ],
    )

    content = AgentService().respond("Check your health.")

    assert content == "My voice check is failing."
    assert client.calls == 0



def test_agent_does_not_run_health_check_for_story_about_status(
    monkeypatch,
    tmp_path,
) -> None:
    """
    Verify that story requests do not trigger diagnostics because they mention status.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = StoryClient()
    patch_agent(monkeypatch, client=client, tmp_path=tmp_path)
    monkeypatch.setattr(
        "app.tools.health_tools.run_health_checks",
        lambda: (_ for _ in ()).throw(AssertionError("health check should not run")),
    )

    content = AgentService().respond("Tell me a story about a status light.")

    assert content == "Once upon a protocol, a light learned restraint."
    assert client.calls == 1



def test_agent_does_not_run_health_check_for_status_question(
    monkeypatch,
    tmp_path,
) -> None:
    """
    Verify that status questions do not trigger diagnostics without explicit words.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = StatusAnswerClient()
    patch_agent(monkeypatch, client=client, tmp_path=tmp_path)
    monkeypatch.setattr(
        "app.tools.health_tools.run_health_checks",
        lambda: (_ for _ in ()).throw(AssertionError("health check should not run")),
    )

    content = AgentService().respond("What is your status?")

    assert content == "Operational enough. A triumph by local standards."
    assert client.calls == 1



def test_agent_runs_health_check_for_explicit_diagnostics_request(
    monkeypatch,
    tmp_path,
) -> None:
    """
    Verify that explicit diagnostics wording runs health diagnostics.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = HealthSummaryClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )
    monkeypatch.setattr(
        "app.tools.health_tools.run_health_checks",
        lambda: [
            SimpleNamespace(name="database", ok=True, detail="Database is reachable."),
        ],
    )

    content = AgentService().respond("Run diagnostics.")

    assert content == "My diagnostics are clear. No issues were found."
    assert client.calls == 0



def test_agent_health_summary_omits_passing_checks_when_everything_is_ok(
    monkeypatch,
    tmp_path,
) -> None:
    """
    Verify that agent health summary omits passing checks when everything is ok.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = HealthSummaryClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )
    monkeypatch.setattr(
        "app.tools.health_tools.run_health_checks",
        lambda: [
            SimpleNamespace(name="database", ok=True, detail="Database is reachable."),
            SimpleNamespace(name="voice", ok=True, detail="Voice backend is ready."),
        ],
    )

    content = AgentService().respond("Check your health.")

    assert content == "My diagnostics are clear. No issues were found."
    assert "Database is reachable." not in content
    assert "Voice backend is ready." not in content
    assert client.calls == 0


