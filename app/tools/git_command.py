from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.tools.workspace_context import effective_workspace_root


@dataclass(frozen=True, slots=True)
class GitCommandResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True, slots=True)
class OpenPullRequest:
    number: int
    url: str
    title: str
    branch: str


def resolve_executable(name: str) -> str | None:
    """
    Resolve a git or gh executable path.

    Args:
        name: Executable name (`git` or `gh`).

    Returns:
        Resolved executable path, or None when not found.
    """
    settings = get_settings()
    configured = settings.git_executable if name == "git" else settings.github_cli_path
    configured_text = str(configured or "").strip()
    if configured_text:
        configured_path = Path(configured_text)
        if configured_path.exists():
            return str(configured_path)

    found = shutil.which(name)
    if found:
        return found

    if os.name != "nt":
        return None

    candidates: list[Path] = []
    if name == "git":
        candidates = [
            Path(r"C:\Program Files\Git\cmd\git.exe"),
            Path(r"C:\Program Files\Git\bin\git.exe"),
        ]
    elif name == "gh":
        candidates = [Path(r"C:\Program Files\GitHub CLI\gh.exe")]
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            candidates.append(Path(local_app_data) / "Programs" / "GitHub CLI" / "gh.exe")

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def git_missing_message() -> str:
    """
    Return installation guidance when git is unavailable.

    Returns:
        Human-readable installation message.
    """
    return (
        "Git is not installed or not on PATH. "
        "Install Git for Windows or set GIT_EXECUTABLE in .env."
    )


def gh_missing_message() -> str:
    """
    Return installation guidance when gh is unavailable.

    Returns:
        Human-readable installation message.
    """
    return (
        "GitHub CLI (gh) is not installed or not on PATH. "
        "Install it from https://cli.github.com/ or set GITHUB_CLI_PATH in .env, "
        "then run gh auth login."
    )


def run_git(*args: str) -> GitCommandResult:
    """
    Run a git command in the workspace root.

    Args:
        args: Git subcommand and arguments.

    Returns:
        Captured process result.
    """
    return _run_command("git", list(args))


def run_gh(*args: str) -> GitCommandResult:
    """
    Run a gh CLI command in the workspace root.

    Args:
        args: GitHub CLI subcommand and arguments.

    Returns:
        Captured process result.
    """
    return _run_command("gh", list(args))


def format_command_result(result: GitCommandResult) -> str:
    """
    Format a git/gh command result for error messages.

    Args:
        result: Command result to format.

    Returns:
        Human-readable output string.
    """
    parts = [f"exit code: {result.returncode}"]
    if result.stdout.strip():
        parts.append(f"stdout:\n{result.stdout.strip()}")
    if result.stderr.strip():
        parts.append(f"stderr:\n{result.stderr.strip()}")
    return "\n".join(parts)


def _run_command(executable_name: str, args: list[str]) -> GitCommandResult:
    resolved = resolve_executable(executable_name)
    if resolved is None:
        missing_message = git_missing_message() if executable_name == "git" else gh_missing_message()
        return GitCommandResult(returncode=127, stdout="", stderr=missing_message)

    try:
        process = subprocess.run(
            [resolved, *args],
            cwd=effective_workspace_root(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        return GitCommandResult(returncode=127, stdout="", stderr=str(exc))

    return GitCommandResult(
        returncode=process.returncode,
        stdout=_normalize_output(process.stdout),
        stderr=_normalize_output(process.stderr),
    )


def _normalize_output(value: str | None) -> str:
    return value if isinstance(value, str) else ""
