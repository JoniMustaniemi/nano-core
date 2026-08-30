from app.deploy.update import UpdateCheckResult
from app.deploy.update_state import UpdateStore


def _behind_result(remote_sha: str = "remote123") -> UpdateCheckResult:
    return UpdateCheckResult(
        behind=True,
        commits_behind=2,
        local_sha="local123",
        remote_sha=remote_sha,
        branch="main",
        message="2 commit(s) available on origin/main.",
    )


def test_update_store_prompts_for_new_remote_after_baseline() -> None:
    store = UpdateStore()
    store.set_session_baseline("baseline123")

    assert store.should_prompt("remote456") is True


def test_update_store_skips_session_baseline_remote() -> None:
    store = UpdateStore()
    store.set_session_baseline("baseline123")

    assert store.should_prompt("baseline123") is False


def test_update_store_skips_dismissed_remote() -> None:
    store = UpdateStore()
    store.set_session_baseline("baseline123")
    store.dismiss("remote456")

    assert store.should_prompt("remote456") is False


def test_update_store_skips_after_prompt_offered() -> None:
    store = UpdateStore()
    store.set_session_baseline("baseline123")
    store.mark_prompt_offered("remote456")

    assert store.should_prompt("remote456") is False


def test_update_store_snapshot_reflects_last_check() -> None:
    store = UpdateStore()
    result = _behind_result()
    store.record_check(result)

    snapshot = store.snapshot()

    assert snapshot.available is True
    assert snapshot.commits_behind == 2
    assert snapshot.remote_sha == "remote123"
