from types import SimpleNamespace

import pytest

from app.tools import git_github
from app.tools.git_github import ensure_feature_branch


def test_ensure_feature_branch_checks_out_existing_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run_git(*args: str):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("app.tools.git_github.branch_exists", lambda name: True)
    monkeypatch.setattr("app.tools.git_github.run_git", fake_run_git)

    result = ensure_feature_branch("feature/add_github_pr")

    assert result.returncode == 0
    assert calls == [("checkout", "feature/add_github_pr")]


def test_ensure_feature_branch_creates_missing_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run_git(*args: str):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("app.tools.git_github.branch_exists", lambda name: False)
    monkeypatch.setattr("app.tools.git_github.run_git", fake_run_git)

    result = ensure_feature_branch("feature/add_github_pr")

    assert result.returncode == 0
    assert calls == [("checkout", "-b", "feature/add_github_pr")]


def test_resolve_executable_finds_git_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.tools.git_github.get_settings",
        lambda: type("Settings", (), {"git_executable": "", "github_cli_path": ""})(),
    )
    monkeypatch.setattr("app.tools.git_github.shutil.which", lambda name: None)
    monkeypatch.setattr("app.tools.git_github.os.name", "nt")
    monkeypatch.setattr(
        "app.tools.git_github.Path.exists",
        lambda self: str(self).endswith("Git\\cmd\\git.exe"),
    )

    resolved = git_github.resolve_executable("git")

    assert resolved is not None
    assert resolved.endswith("git.exe")


def test_run_gh_returns_clear_error_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.tools.git_github.resolve_executable", lambda name: None)

    result = git_github.run_gh("--version")

    assert result.returncode == 127
    assert "GitHub CLI" in result.stderr
