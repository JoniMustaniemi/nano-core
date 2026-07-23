from types import SimpleNamespace

import pytest

from app.tools.git_command import resolve_executable, run_gh
from app.tools.git_github import OpenPullRequest, ensure_feature_branch, get_open_pull_request


def test_ensure_feature_branch_checks_out_existing_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run_git(*args: str):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("app.tools.git_ops.branch_exists", lambda name: True)
    monkeypatch.setattr("app.tools.git_ops.run_git", fake_run_git)

    result = ensure_feature_branch("feature/add_github_pr")

    assert result.returncode == 0
    assert calls == [("checkout", "feature/add_github_pr")]


def test_ensure_feature_branch_creates_missing_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run_git(*args: str):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("app.tools.git_ops.branch_exists", lambda name: False)
    monkeypatch.setattr("app.tools.git_ops.run_git", fake_run_git)

    result = ensure_feature_branch("feature/add_github_pr")

    assert result.returncode == 0
    assert calls == [("checkout", "-b", "feature/add_github_pr")]


def test_resolve_executable_finds_git_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.tools.git_command.get_settings",
        lambda: type("Settings", (), {"git_executable": "", "github_cli_path": ""})(),
    )
    monkeypatch.setattr("app.tools.git_command.shutil.which", lambda name: None)
    monkeypatch.setattr("app.tools.git_command.os.name", "nt")
    monkeypatch.setattr(
        "app.tools.git_command.Path.exists",
        lambda self: str(self).endswith("Git\\cmd\\git.exe"),
    )

    resolved = resolve_executable("git")

    assert resolved is not None
    assert resolved.endswith("git.exe")


def test_run_gh_returns_clear_error_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.tools.git_command.resolve_executable", lambda name: None)

    result = run_gh("--version")

    assert result.returncode == 127
    assert "GitHub CLI" in result.stderr


def test_get_open_pull_request_returns_none_when_no_open_prs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.tools.github_ops.run_gh",
        lambda *args: SimpleNamespace(returncode=0, stdout="[]", stderr=""),
    )

    assert get_open_pull_request() is None


def test_get_open_pull_request_parses_first_open_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = (
        '[{"number": 7, "url": "https://github.com/org/repo/pull/7", '
        '"title": "fix timer", "headRefName": "feature/fix_timer"}]'
    )
    monkeypatch.setattr(
        "app.tools.github_ops.run_gh",
        lambda *args: SimpleNamespace(returncode=0, stdout=payload, stderr=""),
    )

    open_pr = get_open_pull_request()

    assert open_pr == OpenPullRequest(
        number=7,
        url="https://github.com/org/repo/pull/7",
        title="fix timer",
        branch="feature/fix_timer",
    )
