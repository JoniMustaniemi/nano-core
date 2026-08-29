from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.config import get_settings
from app.deploy.update import PullResult, install_dependencies, pull_latest


def test_pull_latest_skipped_when_fetch_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AUTO_UPDATE_BRANCH", "main")
    get_settings.cache_clear()

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        result = MagicMock(returncode=1, stdout="", stderr="network error")
        return result

    monkeypatch.setattr("app.deploy.update.subprocess.run", fake_run)

    result = pull_latest(repo_root=tmp_path)

    assert result.updated is False
    assert "network error" in result.message
    get_settings.cache_clear()


def test_pull_latest_skipped_when_merge_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AUTO_UPDATE_BRANCH", "main")
    get_settings.cache_clear()

    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(args)
        if args[:3] == ["git", "fetch", "origin"]:
            return MagicMock(returncode=0, stdout="", stderr="")
        return MagicMock(returncode=1, stdout="", stderr="local changes would be overwritten")

    monkeypatch.setattr("app.deploy.update.subprocess.run", fake_run)

    result = pull_latest(repo_root=tmp_path)

    assert result.updated is False
    assert calls[0] == ["git", "fetch", "origin", "main"]
    assert calls[1] == ["git", "merge", "--ff-only", "origin/main"]
    get_settings.cache_clear()


def test_pull_latest_reports_already_up_to_date(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AUTO_UPDATE_BRANCH", "main")
    get_settings.cache_clear()

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        if args[:3] == ["git", "fetch", "origin"]:
            return MagicMock(returncode=0, stdout="", stderr="")
        return MagicMock(returncode=0, stdout="Already up to date.\n", stderr="")

    monkeypatch.setattr("app.deploy.update.subprocess.run", fake_run)

    result = pull_latest(repo_root=tmp_path)

    assert result == PullResult(updated=False, message="Already up to date.")
    get_settings.cache_clear()


def test_pull_latest_reports_fast_forward(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTO_UPDATE_BRANCH", "main")
    get_settings.cache_clear()

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        if args[:3] == ["git", "fetch", "origin"]:
            return MagicMock(returncode=0, stdout="", stderr="")
        return MagicMock(returncode=0, stdout="Updating abc123..def456\nFast-forward\n", stderr="")

    monkeypatch.setattr("app.deploy.update.subprocess.run", fake_run)

    result = pull_latest(repo_root=tmp_path)

    assert result.updated is True
    assert "Fast-forward" in result.message
    get_settings.cache_clear()


def test_install_dependencies_runs_pip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(args)
        return MagicMock(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("app.deploy.update.subprocess.run", fake_run)
    monkeypatch.setattr("app.deploy.update.sys.executable", "/venv/bin/python")

    assert install_dependencies(repo_root=tmp_path) is True
    assert calls == [["/venv/bin/python", "-m", "pip", "install", "-e", ".[local-llm,voice]"]]
