import json
from types import SimpleNamespace

import pytest

from app.assistant.response_composer import ResponseComposer
from app.assistant.response_source import tool_result_source
from app.tools.pr_service import PrResult, PullRequestService


class _SummaryClient:
    def __init__(self, response: str = "") -> None:
        self.response = response
        self.calls = 0

    def complete(self, messages) -> str:
        self.calls += 1
        return self.response


def test_summarize_pr_result_success_uses_llm() -> None:
    client = _SummaryClient(
        "I opened pull request fix_timer_cancel_bug at https://github.com/org/repo/pull/1."
    )
    composer = ResponseComposer()
    payload = json.dumps(
        {
            "ok": True,
            "step": "complete",
            "url": "https://github.com/org/repo/pull/1",
            "branch": "feature/fix_timer_cancel_bug",
            "title": "fix_timer_cancel_bug",
            "base": "main",
            "verified_with": "python -m pytest -q",
            "error": None,
            "output": None,
        }
    )
    source = tool_result_source(
        user_message="create a PR",
        facts=payload,
        tool_name="create_pull_request",
        conversation_id="default",
    )

    summary = composer.compose(client, source)

    assert "https://github.com/org/repo/pull/1" in summary
    assert client.calls == 1


def test_summarize_pr_result_failure_fallback() -> None:
    client = _SummaryClient("")
    composer = ResponseComposer()
    payload = json.dumps(
        {
            "ok": False,
            "step": "verify",
            "url": None,
            "branch": None,
            "title": None,
            "base": None,
            "verified_with": "python -m pytest -q",
            "error": "Verification failed.",
            "output": "FAILED tests/test_x.py",
        }
    )
    source = tool_result_source(
        user_message="create a PR",
        facts=payload,
        tool_name="create_pull_request",
        conversation_id="default",
    )

    summary = composer.compose(client, source)

    assert "declined to commit" in summary.lower()
    assert "FAILED tests/test_x.py" not in summary


def test_pr_service_verify_failure_does_not_mutate_git(monkeypatch: pytest.MonkeyPatch) -> None:
    git_calls: list[tuple[str, ...]] = []

    def fake_run_git(*args: str):
        git_calls.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("app.tools.pr_service.is_git_repo", lambda: True)
    monkeypatch.setattr("app.tools.pr_service.gh_available", lambda: True)
    monkeypatch.setattr("app.tools.pr_service.gh_authenticated", lambda: True)
    monkeypatch.setattr("app.tools.pr_service.has_publishable_changes", lambda: True)
    monkeypatch.setattr(
        "app.tools.pr_service.collect_change_context",
        lambda: {"changed_files": ["a.py"], "dirty": True},
    )
    monkeypatch.setattr(
        "app.tools.pr_service.run_pr_verification",
        lambda: SimpleNamespace(
            ok=False,
            command=["python", "-m", "pytest", "-q"],
            exit_code=1,
            output="FAILED",
            error="Verification failed.",
        ),
    )
    monkeypatch.setattr("app.tools.pr_service.run_git", fake_run_git)
    monkeypatch.setattr("app.tools.pr_service.activity.working", lambda **kwargs: None)
    monkeypatch.setattr("app.tools.pr_service.activity.log", lambda **kwargs: None)
    monkeypatch.setattr("app.tools.pr_service.activity.error", lambda **kwargs: None)

    result = PullRequestService().run(client=SimpleNamespace())

    assert result.ok is False
    assert result.step == "verify"
    assert not any(call[:2] == ("commit",) or call[:2] == ("push",) for call in git_calls)


def test_pr_service_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    git_calls: list[tuple[str, ...]] = []
    gh_calls: list[tuple[str, ...]] = []
    branch_state = {"name": "main"}

    def fake_run_git(*args: str):
        git_calls.append(args)
        if args[:2] == ("branch", "--show-current"):
            return SimpleNamespace(returncode=0, stdout=f"{branch_state['name']}\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def fake_ensure_feature_branch(name: str):
        git_calls.append(("ensure_feature_branch", name))
        branch_state["name"] = name
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def fake_run_gh(*args: str):
        gh_calls.append(args)
        return SimpleNamespace(
            returncode=0,
            stdout="https://github.com/org/repo/pull/2\n",
            stderr="",
        )

    monkeypatch.setattr("app.tools.pr_service.is_git_repo", lambda: True)
    monkeypatch.setattr("app.tools.pr_service.gh_available", lambda: True)
    monkeypatch.setattr("app.tools.pr_service.gh_authenticated", lambda: True)
    monkeypatch.setattr("app.tools.pr_service.has_publishable_changes", lambda: True)
    monkeypatch.setattr(
        "app.tools.pr_service.collect_change_context",
        lambda: {"changed_files": ["a.py"], "dirty": True},
    )
    monkeypatch.setattr(
        "app.tools.pr_service.run_pr_verification",
        lambda: SimpleNamespace(
            ok=True,
            command=["python", "-m", "pytest", "-q"],
            exit_code=0,
            output="",
            error=None,
        ),
    )
    monkeypatch.setattr("app.tools.pr_service.working_tree_dirty", lambda: True)
    monkeypatch.setattr("app.tools.pr_service.get_current_branch", lambda: branch_state["name"])
    monkeypatch.setattr("app.tools.pr_service.detect_default_base_branch", lambda: "main")
    monkeypatch.setattr("app.tools.pr_service.run_git", fake_run_git)
    monkeypatch.setattr("app.tools.pr_service.run_gh", fake_run_gh)
    monkeypatch.setattr("app.tools.pr_service.ensure_feature_branch", fake_ensure_feature_branch)
    monkeypatch.setattr("app.tools.pr_service.activity.working", lambda **kwargs: None)
    monkeypatch.setattr("app.tools.pr_service.activity.log", lambda **kwargs: None)
    monkeypatch.setattr("app.tools.pr_service.activity.standby", lambda **kwargs: None)

    naming = SimpleNamespace(
        slug="add_github_pr",
        title="add_github_pr",
        commit_message="add_github_pr",
        body="Adds GitHub PR support.",
        branch="feature/add_github_pr",
    )
    service = PullRequestService(
        naming_service=SimpleNamespace(generate=lambda **kwargs: naming),
    )

    result = service.run(client=SimpleNamespace())

    assert result == PrResult(
        ok=True,
        step="complete",
        url="https://github.com/org/repo/pull/2",
        branch="feature/add_github_pr",
        title="add_github_pr",
        base="main",
        verified_with="python -m pytest -q",
        error=None,
        output=None,
    )
    assert ("ensure_feature_branch", "feature/add_github_pr") in git_calls
    assert ("commit", "-m", "add_github_pr") in git_calls
    assert ("push", "-u", "origin", "HEAD") in git_calls
    assert gh_calls[0][:2] == ("pr", "create")
    assert "--head" not in gh_calls[0]
