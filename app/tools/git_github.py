"""Backward-compatible re-exports for git and GitHub helpers."""

from app.tools.git_command import (
    GitCommandResult,
    OpenPullRequest,
    format_command_result,
    gh_missing_message,
    git_missing_message,
    resolve_executable,
    run_gh,
    run_git,
)
from app.tools.git_ops import (
    branch_exists,
    checkout_branch,
    checkout_new_branch,
    collect_change_context,
    ensure_feature_branch,
    ensure_unique_branch_slug,
    get_current_branch,
    has_publishable_changes,
    has_unpushed_commits,
    is_git_repo,
    working_tree_dirty,
)
from app.tools.github_ops import (
    detect_default_base_branch,
    get_open_pull_request,
    gh_authenticated,
    gh_available,
    qualify_head_branch,
)

__all__ = [
    "GitCommandResult",
    "OpenPullRequest",
    "branch_exists",
    "checkout_branch",
    "checkout_new_branch",
    "collect_change_context",
    "detect_default_base_branch",
    "ensure_feature_branch",
    "ensure_unique_branch_slug",
    "format_command_result",
    "get_current_branch",
    "get_open_pull_request",
    "gh_authenticated",
    "gh_available",
    "gh_missing_message",
    "git_missing_message",
    "has_publishable_changes",
    "has_unpushed_commits",
    "is_git_repo",
    "qualify_head_branch",
    "resolve_executable",
    "run_gh",
    "run_git",
    "working_tree_dirty",
]
