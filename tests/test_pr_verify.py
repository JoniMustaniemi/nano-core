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


def test_resolve_lint_command_detects_ruff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.tools.pr_verify.workspace_root", lambda: tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        "[tool.ruff]\nline-length = 100\n",
        encoding="utf-8",
    )

    command = pr_verify.resolve_lint_command()

    assert command == [sys.executable, "-m", "ruff", "check", "app", "tests"]


def test_resolve_lint_command_returns_none_without_ruff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.tools.pr_verify.workspace_root", lambda: tmp_path)

    assert pr_verify.resolve_lint_command() is None


def test_run_pr_lint_skips_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.tools.pr_verify.resolve_lint_command", lambda: None)

    result = pr_verify.run_pr_lint()

    assert result.ok is True
    assert result.command == []


def test_run_pr_lint_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.tools.pr_verify.resolve_lint_command",
        lambda: [sys.executable, "-m", "ruff", "check", "app", "tests"],
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
            {
                "returncode": 1,
                "stdout": "E999 syntax error\nFound 1 error.",
                "stderr": "",
            },
        )(),
    )

    result = pr_verify.run_pr_lint()

    assert result.ok is False
    assert "E999" in result.output
    assert result.error == "Lint checks failed."
    assert result.auto_fixed is False


def test_run_pr_lint_auto_fixes_fixable_issues(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.tools.pr_verify.resolve_lint_command",
        lambda: [sys.executable, "-m", "ruff", "check", "app", "tests"],
    )
    monkeypatch.setattr(
        "app.tools.pr_verify.get_settings",
        lambda: type("Settings", (), {"github_pr_verify_timeout_seconds": 30})(),
    )
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[-1] == "--fix":
            return type("Process", (), {"returncode": 0, "stdout": "Fixed 4 errors.", "stderr": ""})()
        if len(calls) == 1:
            return type(
                "Process",
                (),
                {
                    "returncode": 1,
                    "stdout": (
                        "F401 [*] unused import\n"
                        "Found 4 errors.\n"
                        "[*] 4 fixable with the `--fix` option."
                    ),
                    "stderr": "",
                },
            )()
        return type("Process", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr("app.tools.pr_verify.subprocess.run", fake_run)

    result = pr_verify.run_pr_lint()

    assert result.ok is True
    assert result.auto_fixed is True
    assert calls[1] == [sys.executable, "-m", "ruff", "check", "app", "tests", "--fix"]
    assert len(calls) == 3


def test_run_pr_lint_auto_fix_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.tools.pr_verify.resolve_lint_command",
        lambda: [sys.executable, "-m", "ruff", "check", "app", "tests"],
    )
    monkeypatch.setattr(
        "app.tools.pr_verify.get_settings",
        lambda: type("Settings", (), {"github_pr_verify_timeout_seconds": 30})(),
    )

    def fake_run(command, **kwargs):
        if command[-1] == "--fix":
            return type("Process", (), {"returncode": 1, "stdout": "fix failed", "stderr": ""})()
        return type(
            "Process",
            (),
            {
                "returncode": 1,
                "stdout": "F401 [*] unused import\n[*] 1 fixable with the `--fix` option.",
                "stderr": "",
            },
        )()

    monkeypatch.setattr("app.tools.pr_verify.subprocess.run", fake_run)

    result = pr_verify.run_pr_lint()

    assert result.ok is False
    assert result.error == "Lint auto-fix failed."
    assert "fix failed" in result.output


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
