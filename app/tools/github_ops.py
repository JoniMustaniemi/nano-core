from __future__ import annotations

import json

from app.config import get_settings
from app.tools.git_command import OpenPullRequest, run_gh, run_git


def gh_available() -> bool:
    """
    Return whether the gh CLI is available.

    Returns:
        True when gh responds to --version.
    """
    from app.tools.git_command import resolve_executable

    if resolve_executable("gh") is None:
        return False
    result = run_gh("--version")
    return result.returncode == 0


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
