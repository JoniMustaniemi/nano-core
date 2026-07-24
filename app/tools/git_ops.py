from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any

from app.tools.git_command import GitCommandResult, run_git

_SLUG_MAX_LEN = 48


def is_git_repo() -> bool:
    """
    Return whether the workspace is inside a git repository.

    Returns:
        True when the workspace is a git repository.
    """
    result = run_git("rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"


def get_current_branch() -> str:
    """
    Return the current git branch name.

    Returns:
        Current branch name.

    Raises:
        RuntimeError: If the branch cannot be determined.
    """
    result = run_git("branch", "--show-current")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Could not determine current branch.")
    branch = result.stdout.strip()
    if not branch:
        raise RuntimeError("Detached HEAD state is not supported for pull requests.")
    return branch


def working_tree_dirty() -> bool:
    """
    Return whether the working tree has uncommitted changes.

    Returns:
        True when there are staged or unstaged changes.
    """
    result = run_git("status", "--porcelain")
    return result.returncode == 0 and bool(result.stdout.strip())


def has_unpushed_commits() -> bool:
    """
    Return whether the current branch has unpushed commits.

    Returns:
        True when commits exist that are not on the upstream branch.
    """
    result = run_git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if result.returncode != 0:
        return bool(run_git("log", "origin/HEAD..HEAD", "--oneline").stdout.strip())

    ahead = run_git("rev-list", "--count", "@{u}..HEAD")
    if ahead.returncode != 0:
        return False
    return int(ahead.stdout.strip() or "0") > 0


def has_publishable_changes() -> bool:
    """
    Return whether there is something to publish.

    Returns:
        True when the tree is dirty or has unpushed commits.
    """
    return working_tree_dirty() or has_unpushed_commits()


def branch_exists(name: str) -> bool:
    """
    Return whether a branch exists locally or on origin.

    Args:
        name: Branch name to check.

    Returns:
        True when the branch exists locally or on origin.
    """
    local = run_git("show-ref", "--verify", "--quiet", f"refs/heads/{name}")
    if local.returncode == 0:
        return True
    remote = run_git("show-ref", "--verify", "--quiet", f"refs/remotes/origin/{name}")
    return remote.returncode == 0


def checkout_new_branch(name: str) -> GitCommandResult:
    """
    Create and switch to a new branch.

    Args:
        name: Branch name to create.

    Returns:
        Git command result.
    """
    return run_git("checkout", "-b", name)


def checkout_branch(name: str) -> GitCommandResult:
    """
    Switch to an existing branch.

    Args:
        name: Branch name to check out.

    Returns:
        Git command result.
    """
    return run_git("checkout", name)


def ensure_feature_branch(name: str) -> GitCommandResult:
    """
    Switch to a feature branch, creating it when needed.

    Args:
        name: Branch name to use.

    Returns:
        Git command result.
    """
    if branch_exists(name):
        return checkout_branch(name)
    return checkout_new_branch(name)


def _append_slug_suffix(base: str, suffix: str) -> str:
    """
    Append a suffix to a branch slug while respecting max length.

    Args:
        base: Base snake_case slug.
        suffix: Suffix without a leading underscore.

    Returns:
        Combined slug capped at 48 characters.
    """
    combined = f"{base}_{suffix}"
    if len(combined) <= _SLUG_MAX_LEN:
        return combined
    trimmed_base = base[: _SLUG_MAX_LEN - len(suffix) - 1].rstrip("_")
    return f"{trimmed_base}_{suffix}"


def ensure_unique_branch_slug(slug: str) -> str:
    """
    Ensure a feature branch slug is unique locally and on origin.

    When the base slug is taken, appends a short date or random token instead
    of only incrementing _2, _3, and so on.

    Args:
        slug: Base snake_case slug.

    Returns:
        Unique slug suitable for feature/{slug}.
    """
    if not branch_exists(f"feature/{slug}"):
        return slug

    date_suffix = datetime.now(UTC).strftime("%m%d")
    dated = _append_slug_suffix(slug, date_suffix)
    if not branch_exists(f"feature/{dated}"):
        return dated

    for _ in range(10):
        token = secrets.token_hex(2)
        candidate = _append_slug_suffix(slug, token)
        if not branch_exists(f"feature/{candidate}"):
            return candidate

    suffix = 2
    candidate = slug
    while branch_exists(f"feature/{candidate}"):
        candidate = _append_slug_suffix(slug, str(suffix))
        suffix += 1
    return candidate


def collect_change_context() -> dict[str, Any]:
    """
    Collect git change context for naming and PR body generation.

    Returns:
        Dictionary with diff metadata and recent commits.
    """
    from app.config import get_settings

    settings = get_settings()
    max_chars = settings.pr_naming_diff_max_chars

    diff_stat = _stdout_or_empty("diff", "--stat")
    diff_patch = _stdout_or_empty("diff")
    if len(diff_patch) > max_chars:
        diff_patch = diff_patch[:max_chars] + "\n... (truncated)"

    staged_stat = _stdout_or_empty("diff", "--cached", "--stat")
    name_status = _stdout_or_empty("diff", "--name-only")
    changed_files = [line.strip() for line in name_status.splitlines() if line.strip()]

    recent_commits = _stdout_or_empty("log", "--oneline", "-5")
    unpushed = (
        run_git("log", "@{u}..HEAD", "--oneline")
        if _has_upstream()
        else run_git("log", "--oneline", "-5")
    )
    unpushed_commits = [line.strip() for line in unpushed.stdout.splitlines() if line.strip()]

    return {
        "diff_stat": diff_stat,
        "staged_stat": staged_stat,
        "diff_patch": diff_patch,
        "changed_files": changed_files,
        "recent_commits": recent_commits,
        "unpushed_commits": unpushed_commits,
        "current_branch": get_current_branch(),
        "dirty": working_tree_dirty(),
        "has_unpushed_commits": has_unpushed_commits(),
    }


def _stdout_or_empty(*args: str) -> str:
    result = run_git(*args)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _has_upstream() -> bool:
    result = run_git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    return result.returncode == 0 and bool(result.stdout.strip())
