from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


def is_git_repo() -> bool:
    """
    Return whether the workspace is inside a git repository.

    Returns:
        True when the workspace is a git repository.
    """
    result = run_git("rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"


def gh_available() -> bool:
    """
    Return whether the gh CLI is available.

    Returns:
        True when gh responds to --version.
    """
    if resolve_executable("gh") is None:
        return False
    result = run_gh("--version")
    return result.returncode == 0


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
    if configured.strip():
        configured_path = Path(configured.strip())
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


def gh_authenticated() -> bool:
    """
    Return whether gh is authenticated.

    Returns:
        True when gh auth status succeeds.
    """
    result = run_gh("auth", "status")
    return result.returncode == 0


def get_open_pull_request() -> OpenPullRequest | None:
    """
    Return the oldest open pull request for this repo, if any.

    Returns:
        Open pull request metadata when one exists; otherwise None.
    """
    result = run_gh(
        "pr",
        "list",
        "--state",
        "open",
        "--limit",
        "1",
        "--json",
        "number,url,title,headRefName",
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        items = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(items, list) or not items:
        return None
    item = items[0]
    if not isinstance(item, dict):
        return None
    number = item.get("number")
    url = item.get("url")
    title = item.get("title")
    branch = item.get("headRefName")
    if not isinstance(number, int) or not isinstance(url, str) or not url:
        return None
    return OpenPullRequest(
        number=number,
        url=url,
        title=str(title or "").strip() or f"PR #{number}",
        branch=str(branch or "").strip(),
    )


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


def detect_default_base_branch() -> str:
    """
    Detect the repository default branch.

    Returns:
        Default base branch name.
    """
    settings = get_settings()
    symbolic = run_git("symbolic-ref", "refs/remotes/origin/HEAD")
    if symbolic.returncode == 0:
        ref = symbolic.stdout.strip()
        if ref.startswith("refs/remotes/origin/"):
            return ref.removeprefix("refs/remotes/origin/")

    gh_view = run_gh("repo", "view", "--json", "defaultBranchRef")
    if gh_view.returncode == 0:
        try:
            payload = json.loads(gh_view.stdout)
            name = payload.get("defaultBranchRef", {}).get("name")
            if isinstance(name, str) and name:
                return name
        except json.JSONDecodeError:
            pass

    return settings.github_default_base_branch


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


def qualify_head_branch(branch: str) -> str:
    """
    Build a head branch reference for gh when owner qualification is required.

    Args:
        branch: Local branch name.

    Returns:
        Qualified head branch when owner is known; otherwise the branch name.
    """
    view = run_gh("repo", "view", "--json", "nameWithOwner")
    if view.returncode != 0:
        return branch
    try:
        payload = json.loads(view.stdout)
        name_with_owner = payload.get("nameWithOwner")
        if isinstance(name_with_owner, str) and "/" in name_with_owner:
            owner = name_with_owner.split("/", 1)[0]
            return f"{owner}:{branch}"
    except json.JSONDecodeError:
        pass
    return branch


def checkout_branch(name: str) -> GitCommandResult:
    """
    Switch to an existing branch.

    Args:
        name: Branch name to check out.

    Returns:
        Git command result.
    """
    return run_git("checkout", name)


def collect_change_context() -> dict[str, Any]:
    """
    Collect git change context for naming and PR body generation.

    Returns:
        Dictionary with diff metadata and recent commits.
    """
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
    unpushed = run_git("log", "@{u}..HEAD", "--oneline") if _has_upstream() else run_git(
        "log", "--oneline", "-5"
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


def ensure_unique_branch_slug(slug: str) -> str:
    """
    Ensure a feature branch slug is unique locally and on origin.

    Args:
        slug: Base snake_case slug.

    Returns:
        Unique slug, with numeric suffix when needed.
    """
    candidate = slug
    suffix = 2
    while branch_exists(f"feature/{candidate}"):
        candidate = f"{slug}_{suffix}"
        suffix += 1
    return candidate


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
        )
    except FileNotFoundError as exc:
        return GitCommandResult(returncode=127, stdout="", stderr=str(exc))

    return GitCommandResult(
        returncode=process.returncode,
        stdout=process.stdout,
        stderr=process.stderr,
    )


def _stdout_or_empty(*args: str) -> str:
    result = run_git(*args)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _has_upstream() -> bool:
    result = run_git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    return result.returncode == 0 and bool(result.stdout.strip())
