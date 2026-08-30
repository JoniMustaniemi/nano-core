import pytest

from app.config import get_settings
from app.deploy.update import UpdateCheckResult
from app.deploy.update_state import update_store
from app.scheduler.jobs import check_for_available_updates


def _behind_result(remote_sha: str = "remote456") -> UpdateCheckResult:
    return UpdateCheckResult(
        behind=True,
        commits_behind=1,
        local_sha="local123",
        remote_sha=remote_sha,
        branch="main",
        message="1 commit(s) available on origin/main.",
    )


@pytest.fixture(autouse=True)
def reset_update_store() -> None:
    update_store.reset()
    update_store.set_session_baseline("baseline123")


def test_check_for_available_updates_skips_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UPDATE_CHECK_ENABLED", "false")
    get_settings.cache_clear()
    offers: list[UpdateCheckResult] = []
    monkeypatch.setattr(
        "app.scheduler.jobs.check_for_updates",
        lambda repo_root=None: _behind_result(),
    )
    monkeypatch.setattr(
        "app.scheduler.jobs.update_interaction_handler.offer_update",
        lambda *, result, conversation_id="default": offers.append(result),
    )

    check_for_available_updates()

    assert offers == []
    get_settings.cache_clear()


def test_check_for_available_updates_offers_when_behind(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UPDATE_CHECK_ENABLED", "true")
    get_settings.cache_clear()
    offers: list[UpdateCheckResult] = []
    monkeypatch.setattr(
        "app.scheduler.jobs.check_for_updates",
        lambda repo_root=None: _behind_result(),
    )
    monkeypatch.setattr(
        "app.scheduler.jobs.update_interaction_handler.offer_update",
        lambda *, result, conversation_id="default": offers.append(result),
    )

    check_for_available_updates()

    assert len(offers) == 1
    assert offers[0].remote_sha == "remote456"
    get_settings.cache_clear()


def test_check_for_available_updates_skips_when_not_behind(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UPDATE_CHECK_ENABLED", "true")
    get_settings.cache_clear()
    offers: list[UpdateCheckResult] = []
    monkeypatch.setattr(
        "app.scheduler.jobs.check_for_updates",
        lambda repo_root=None: UpdateCheckResult(
            behind=False,
            commits_behind=0,
            local_sha="abc",
            remote_sha="abc",
            branch="main",
            message="Already up to date.",
        ),
    )
    monkeypatch.setattr(
        "app.scheduler.jobs.update_interaction_handler.offer_update",
        lambda *, result, conversation_id="default": offers.append(result),
    )

    check_for_available_updates()

    assert offers == []
    get_settings.cache_clear()
