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


def pull_latest(repo_root: Path | None = None) -> PullResult:
    """Fast-forward the local branch to origin. Never raises; logs and returns on failure."""
    settings = get_settings()
    branch = settings.auto_update_branch.strip() or "main"
    root = repo_root or Path.cwd()

    try:
        fetch = subprocess.run(
            ["git", "fetch", "origin", branch],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if fetch.returncode != 0:
            message = (fetch.stderr or fetch.stdout or "git fetch failed").strip()
            logger.warning("Auto-update skipped: fetch failed: %s", message)
            return PullResult(updated=False, message=message)

        merge = subprocess.run(
            ["git", "merge", "--ff-only", f"origin/{branch}"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
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
