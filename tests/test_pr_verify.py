import sys
from pathlib import Path

import pytest

from app.tools import pr_verify


def test_resolve_verify_command_detects_pytest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.tools.pr_verify.get_settings",
        lambda: type(
            "Settings",
            (),
            {"github_pr_verify_command": ""},
        )(),
    )
    monkeypatch.setattr("app.tools.pr_verify.workspace_root", lambda: tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = ['tests']\n",
        encoding="utf-8",
    )

    command = pr_verify.resolve_verify_command()

    assert command == [sys.executable, "-m", "pytest", "-q"]


def test_resolve_verify_command_uses_config_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.tools.pr_verify.get_settings",
        lambda: type(
            "Settings",
            (),
            {"github_pr_verify_command": "python -m pytest -q tests/test_health.py"},
        )(),
    )
    monkeypatch.setattr("app.tools.pr_verify.workspace_root", lambda: tmp_path)

    command = pr_verify.resolve_verify_command()

    assert command == ["python", "-m", "pytest", "-q", "tests/test_health.py"]


def test_resolve_verify_command_returns_none_without_match(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.tools.pr_verify.get_settings",
        lambda: type(
            "Settings",
            (),
            {"github_pr_verify_command": ""},
        )(),
    )
    monkeypatch.setattr("app.tools.pr_verify.workspace_root", lambda: tmp_path)

    assert pr_verify.resolve_verify_command() is None


def test_run_pr_verification_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.tools.pr_verify.resolve_verify_command",
        lambda: ["python", "-m", "pytest", "-q"],
    )
    monkeypatch.setattr(
        "app.tools.pr_verify.get_settings",
        lambda: type("Settings", (), {"github_pr_verify_timeout_seconds": 30})(),
    )
    monkeypatch.setattr(
        "app.tools.pr_verify.subprocess.run",
        lambda *args, **kwargs: type("Process", (), {"returncode": 0, "stdout": "ok", "stderr": ""})(),
    )

    result = pr_verify.run_pr_verification()

    assert result.ok is True
    assert result.command == ["python", "-m", "pytest", "-q"]


def test_run_pr_verification_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.tools.pr_verify.resolve_verify_command",
        lambda: ["python", "-m", "pytest", "-q"],
    )
    monkeypatch.setattr(
        "app.tools.pr_verify.get_settings",
        lambda: type("Settings", (), {"github_pr_verify_timeout_seconds": 30})(),
    )
    monkeypatch.setattr(
        "app.tools.pr_verify.subprocess.run",
        lambda *args, **kwargs: type(
            "Process",
            (),
            {"returncode": 1, "stdout": "", "stderr": "FAILED"},
        )(),
    )

    result = pr_verify.run_pr_verification()

    assert result.ok is False
    assert "FAILED" in result.output
