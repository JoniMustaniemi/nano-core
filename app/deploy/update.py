from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PullResult:
    updated: bool
    message: str


@dataclass(frozen=True, slots=True)
class UpdateCheckResult:
    behind: bool
    commits_behind: int
    local_sha: str
    remote_sha: str
    branch: str
    message: str


def _configured_branch() -> str:
    return get_settings().auto_update_branch.strip() or "main"


def _run_git(args: list[str], *, repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )


def _read_git_output(result: subprocess.CompletedProcess[str]) -> str:
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "git command failed").strip()
        raise RuntimeError(message)
    return (result.stdout or "").strip()


def check_for_updates(repo_root: Path | None = None) -> UpdateCheckResult:
    """Fetch origin and report whether the local branch is behind."""
    branch = _configured_branch()
    root = repo_root or Path.cwd()

    try:
        fetch = _run_git(["fetch", "origin", branch], repo_root=root)
        if fetch.returncode != 0:
            message = (fetch.stderr or fetch.stdout or "git fetch failed").strip()
            logger.warning("Update check skipped: fetch failed: %s", message)
            return UpdateCheckResult(
                behind=False,
                commits_behind=0,
                local_sha="",
                remote_sha="",
                branch=branch,
                message=message,
            )

        local_sha = _read_git_output(_run_git(["rev-parse", "HEAD"], repo_root=root))
        remote_ref = f"origin/{branch}"
        remote_sha = _read_git_output(_run_git(["rev-parse", remote_ref], repo_root=root))
        count_output = _read_git_output(
            _run_git(["rev-list", "--count", f"HEAD..{remote_ref}"], repo_root=root)
        )
        commits_behind = int(count_output)
        behind = commits_behind > 0
        if behind:
            message = f"{commits_behind} commit(s) available on origin/{branch}."
        else:
            message = "Already up to date."
        return UpdateCheckResult(
            behind=behind,
            commits_behind=commits_behind,
            local_sha=local_sha,
            remote_sha=remote_sha,
            branch=branch,
            message=message,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        logger.warning("Update check skipped: %s", exc)
        return UpdateCheckResult(
            behind=False,
            commits_behind=0,
            local_sha="",
            remote_sha="",
            branch=branch,
            message=str(exc),
        )


def record_session_baseline(repo_root: Path | None = None) -> None:
    """Record the current origin tip as the session baseline for update prompts."""
    from app.deploy.update_state import update_store

    result = check_for_updates(repo_root=repo_root)
    update_store.record_check(result)
    update_store.set_session_baseline(result.remote_sha or None)


def pull_latest(repo_root: Path | None = None) -> PullResult:
    """Fast-forward the local branch to origin. Never raises; logs and returns on failure."""
    branch = _configured_branch()
    root = repo_root or Path.cwd()

    try:
        fetch = _run_git(["fetch", "origin", branch], repo_root=root)
        if fetch.returncode != 0:
            message = (fetch.stderr or fetch.stdout or "git fetch failed").strip()
            logger.warning("Auto-update skipped: fetch failed: %s", message)
            return PullResult(updated=False, message=message)

        merge = _run_git(["merge", "--ff-only", f"origin/{branch}"], repo_root=root)
        if merge.returncode != 0:
            message = (merge.stderr or merge.stdout or "git merge failed").strip()
            logger.warning("Auto-update skipped: %s", message)
            return PullResult(updated=False, message=message)

        stdout = (merge.stdout or "").strip()
        if "Already up to date" in stdout:
            logger.info("Auto-update: already on latest %s", branch)
            return PullResult(updated=False, message="Already up to date.")

        logger.info("Auto-update: fast-forwarded to latest %s", branch)
        return PullResult(updated=True, message=stdout or "Updated.")
    except OSError as exc:
        logger.warning("Auto-update skipped: %s", exc)
        return PullResult(updated=False, message=str(exc))


def install_dependencies(repo_root: Path | None = None) -> bool:
    """Reinstall editable extras after a pull. Returns True when pip succeeds."""
    root = repo_root or Path.cwd()
    python = sys.executable

    try:
        result = subprocess.run(
            [python, "-m", "pip", "install", "-e", ".[local-llm,voice]"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "pip install failed").strip()
            logger.warning("Auto-update install skipped: %s", message)
            return False

        logger.info("Auto-update: dependencies installed")
        return True
    except OSError as exc:
        logger.warning("Auto-update install skipped: %s", exc)
        return False
