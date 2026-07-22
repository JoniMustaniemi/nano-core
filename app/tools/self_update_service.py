from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from app.config import get_settings
from app.runtime.activity import activity
from app.runtime.status_copy import PULLING_CHANGES_TITLE, SWITCHING_BRANCH_TITLE
from app.tools.git_github import (
  checkout_branch,
  format_command_result,
  get_current_branch,
  is_git_repo,
  run_git,
  working_tree_dirty,
)


@dataclass(frozen=True, slots=True)
class SelfUpdateResult:
  ok: bool
  step: str
  changed_files: list[str] | None = None
  reload_expected: bool = False
  output: str | None = None
  error: str | None = None

  def to_json(self) -> str:
    return json.dumps(asdict(self), ensure_ascii=False)


class SelfUpdateService:
  """Pull latest changes for dev reload."""

  def run(self) -> SelfUpdateResult:
    settings = get_settings()
    base_branch = settings.self_update_base_branch or settings.github_default_base_branch

    activity.working(
      title=PULLING_CHANGES_TITLE,
      detail=f"Updating from origin/{base_branch}.",
      source="tools.self_update_service",
    )

    if not is_git_repo():
      return SelfUpdateResult(ok=False, step="preflight", error="Workspace is not a git repository.")

    if working_tree_dirty():
      return SelfUpdateResult(
        ok=False,
        step="preflight",
        error="Working tree has uncommitted changes. Commit or stash them first.",
      )

    current_branch = get_current_branch()
    if current_branch != base_branch:
      activity.working(
        title=SWITCHING_BRANCH_TITLE,
        detail=f"Moving from {current_branch} to {base_branch} before pulling updates.",
        source="tools.self_update_service",
      )
      checkout_result = checkout_branch(base_branch)
      if checkout_result.returncode != 0:
        return SelfUpdateResult(
          ok=False,
          step="checkout",
          error=format_command_result(checkout_result),
        )

    fetch_result = run_git("fetch", "origin")
    if fetch_result.returncode != 0:
      return SelfUpdateResult(
        ok=False,
        step="fetch",
        error=format_command_result(fetch_result),
      )

    pull_result = run_git("pull", "origin", base_branch)
    if pull_result.returncode != 0:
      return SelfUpdateResult(
        ok=False,
        step="pull",
        error=format_command_result(pull_result),
      )

    diff_result = run_git("diff", "--name-only", "HEAD@{1}", "HEAD")
    changed_files = [
      line.strip()
      for line in diff_result.stdout.splitlines()
      if line.strip()
    ]
    reload_expected = any(path.startswith("app/") for path in changed_files)

    return SelfUpdateResult(
      ok=True,
      step="complete",
      changed_files=changed_files,
      reload_expected=reload_expected,
      output=pull_result.stdout.strip() or pull_result.stderr.strip(),
    )
