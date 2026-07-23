from __future__ import annotations

import re
import subprocess
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from app.tools.git_github import (
    GitCommandResult,
    branch_exists,
    detect_default_base_branch,
    format_command_result,
    is_git_repo,
    resolve_executable,
)
from app.tools.pr_naming import sanitize_slug
from app.tools.workspace_context import workspace_override, workspace_root


@dataclass(frozen=True, slots=True)
class WorktreeSetup:
    worktree: SelfImproveWorktree | None
    error: str | None = None


class SelfImproveWorktree:
    """Temporary git worktree for self-improvement while dev auto-reload is on."""

    def __init__(self, *, path: Path, branch: str) -> None:
        self.path = path.resolve()
        self.branch = branch

    @classmethod
    def try_setup(cls, *, goal: str) -> WorktreeSetup:
        """
        Create a worktree for an isolated self-improvement run.

        Args:
            goal: Self-improvement goal used to derive the branch name.

        Returns:
            Setup result with a worktree or an error message.
        """
        if not is_git_repo():
            return WorktreeSetup(
                worktree=None,
                error="Workspace is not a git repository.",
            )

        branch = _unique_self_improve_branch(goal)
        worktree_id = uuid.uuid4().hex[:8]
        path = workspace_root() / ".nano-worktrees" / f"self-improve-{worktree_id}"
        base_branch = detect_default_base_branch()

        add_result = _run_git_main("worktree", "add", "-b", branch, str(path), base_branch)
        if add_result.returncode != 0:
            return WorktreeSetup(
                worktree=None,
                error=(
                    "Could not create an isolated git worktree for self-improvement. "
                    f"{format_command_result(add_result)}"
                ),
            )

        return WorktreeSetup(worktree=cls(path=path, branch=branch))

    @contextmanager
    def activate(self) -> Iterator[Path]:
        """
        Route workspace operations through this worktree for the duration.

        Yields:
            Resolved worktree root path.
        """
        try:
            with workspace_override(self.path) as active_root:
                yield active_root
        finally:
            _remove_worktree(self.path)


def _unique_self_improve_branch(goal: str) -> str:
    words = re.findall(r"[a-z0-9]+", goal.lower())
    base = sanitize_slug("_".join(words[:6]))[:30] or "update"
    candidate = base
    suffix = 2
    branch_name = f"nano/self-improve-{candidate}"
    while branch_exists(branch_name):
        candidate = f"{base}_{suffix}"
        branch_name = f"nano/self-improve-{candidate}"
        suffix += 1
    return branch_name


def _run_git_main(*args: str) -> GitCommandResult:
    resolved = resolve_executable("git")
    if resolved is None:
        return GitCommandResult(returncode=127, stdout="", stderr="git executable not found")

    try:
        process = subprocess.run(
            [resolved, *args],
            cwd=workspace_root(),
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        return GitCommandResult(returncode=127, stdout="", stderr=str(exc))

    return GitCommandResult(
        returncode=process.returncode,
        stdout=process.stdout,
        stderr=process.stderr,
    )


def _remove_worktree(path: Path) -> None:
    if not path.exists():
        return
    result = _run_git_main("worktree", "remove", "--force", str(path))
    if result.returncode != 0:
        _run_git_main("worktree", "prune")
