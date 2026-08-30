import pytest
from helpers.agent_fixtures import WipeConfirmationClient, agent_respond, patch_agent

from app.assistant.pending import pending_interactions
from app.config import get_settings
from app.deploy.update import PullResult, UpdateCheckResult
from app.deploy.update_state import update_store


@pytest.fixture(autouse=True)
def reset_update_flow_state() -> None:
    update_store.reset()
    pending_interactions.reset()


def _behind_result() -> UpdateCheckResult:
    return UpdateCheckResult(
        behind=True,
        commits_behind=2,
        local_sha="local123",
        remote_sha="remote456",
        branch="main",
        message="2 commit(s) available on origin/main.",
    )


def test_agent_offers_update_confirmation(monkeypatch, tmp_path) -> None:
    patch_agent(monkeypatch, client=WipeConfirmationClient(), tmp_path=tmp_path)
    monkeypatch.setattr(
        "app.assistant.flows.update.check_for_updates",
        lambda repo_root=None: _behind_result(),
    )

    content = agent_respond("Update nano.")

    assert "new version is available" in content.lower()
    assert "yes" in content.lower()
    assert "no" in content.lower()
    assert pending_interactions.get("default") is not None
    assert pending_interactions.get("default").kind == "update_confirmation"


def test_agent_applies_update_after_confirmation(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SERVICE_RESTART_ENABLED", "true")
    get_settings.cache_clear()
    patch_agent(monkeypatch, client=WipeConfirmationClient(), tmp_path=tmp_path)
    monkeypatch.setattr(
        "app.assistant.flows.update.check_for_updates",
        lambda repo_root=None: _behind_result(),
    )
    monkeypatch.setattr(
        "app.assistant.flows.update.pull_latest",
        lambda repo_root=None: PullResult(updated=True, message="Updated."),
    )
    scheduled: list[bool] = []
    monkeypatch.setattr(
        "app.assistant.flows.update.schedule_service_restart",
        lambda: scheduled.append(True) or True,
    )

    agent_respond("Update nano.")
    content = agent_respond("yes")

    assert content == "Updating now. I will restart shortly."
    assert scheduled == [True]
    assert pending_interactions.get("default") is None
    get_settings.cache_clear()


def test_agent_dismisses_update_on_no(monkeypatch, tmp_path) -> None:
    patch_agent(monkeypatch, client=WipeConfirmationClient(), tmp_path=tmp_path)
    monkeypatch.setattr(
        "app.assistant.flows.update.check_for_updates",
        lambda repo_root=None: _behind_result(),
    )

    agent_respond("Update nano.")
    content = agent_respond("no")

    assert content == "Update dismissed."
    assert pending_interactions.get("default") is None


def test_agent_reports_restart_required_when_disabled(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SERVICE_RESTART_ENABLED", "false")
    get_settings.cache_clear()
    patch_agent(monkeypatch, client=WipeConfirmationClient(), tmp_path=tmp_path)
    monkeypatch.setattr(
        "app.assistant.flows.update.check_for_updates",
        lambda repo_root=None: _behind_result(),
    )
    monkeypatch.setattr(
        "app.assistant.flows.update.pull_latest",
        lambda repo_root=None: PullResult(updated=True, message="Updated."),
    )
    monkeypatch.setattr(
        "app.assistant.flows.update.schedule_service_restart",
        lambda: False,
    )

    agent_respond("Update nano.")
    content = agent_respond("yes")

    assert "service restart is disabled" in content.lower()
    get_settings.cache_clear()
