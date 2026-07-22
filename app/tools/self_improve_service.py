from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, cast

from app.assistant.agent_rules import extract_json
from app.config import get_settings
from app.memory import codebase_index
from app.proactive.codebase_files import list_all_app_files
from app.runtime.activity import activity
from app.runtime.status_copy import PLANNING_SELF_IMPROVE_TITLE, VERIFYING_SELF_IMPROVE_TITLE
from app.tools.files import read_text_file, write_text_file
from app.tools.pr_service import PullRequestService
from app.tools.pr_verify import run_pr_verification


@dataclass(frozen=True, slots=True)
class SelfImproveResult:
  ok: bool
  step: str
  changed_files: list[str] | None = None
  pr_url: str | None = None
  goal: str | None = None
  error: str | None = None

  def to_json(self) -> str:
    return json.dumps(asdict(self), ensure_ascii=False)


def _file_selection_lines(goal: str, *, limit: int = 40) -> list[str]:
  records = codebase_index.list_records_for_selection(limit=limit)
  if records:
    lines = [f"- {record.path}: {record.summary}" for record in records if record.summary]
    if lines:
      return lines

  all_paths = list_all_app_files()
  codebase_index.sync_paths(all_paths)
  keywords = [word.lower() for word in goal.split() if len(word) > 3]
  if keywords:
    matched = [
      path
      for path in all_paths
      if any(keyword in path.lower() for keyword in keywords)
    ]
    if matched:
      return [f"- {path}: (not yet scanned)" for path in matched[:limit]]

  return [f"- {path}: (not yet scanned)" for path in all_paths[:limit]]


class SelfImproveService:
  """Orchestrated self-improvement: explore, plan, write, verify, PR."""

  def run(self, *, client: Any, goal: str) -> SelfImproveResult:
    settings = get_settings()
    allowed = settings.self_improve_allowed_prefix

    activity.working(
      title=PLANNING_SELF_IMPROVE_TITLE,
      detail=goal,
      source="tools.self_improve_service",
    )

    selection_lines = _file_selection_lines(goal)
    select_messages = [
      {
        "role": "system",
        "content": (
          "Select files to edit for a self-improvement task. "
          f"Only paths under {allowed} are allowed. "
          'Return JSON only: {"files_to_read": ["app/..."]} with at most '
          f"{settings.self_improve_max_files} paths."
        ),
      },
      {
        "role": "user",
        "content": (
          f"Goal: {goal}\n\nKnown files:\n" + "\n".join(selection_lines)
        ),
      },
    ]
    raw_select = cast(str, client.complete(messages=select_messages)).strip()
    selection = extract_json(raw_select)
    if not isinstance(selection, dict):
      return SelfImproveResult(
        ok=False,
        step="select",
        error="Could not parse file selection from the model.",
        goal=goal,
      )
    files_to_read = selection.get("files_to_read", [])
    if not isinstance(files_to_read, list) or not files_to_read:
      return SelfImproveResult(ok=False, step="select", error="No files selected.", goal=goal)

    file_contents: dict[str, str] = {}
    for raw_path in files_to_read[: settings.self_improve_max_files]:
      path = str(raw_path)
      if not path.startswith(allowed.rstrip("/")):
        continue
      try:
        text = read_text_file(path)
      except (OSError, ValueError):
        continue
      if len(text) > settings.self_improve_max_file_chars:
        text = text[: settings.self_improve_max_file_chars]
      file_contents[path] = text

    if not file_contents:
      return SelfImproveResult(ok=False, step="read", error="Could not read target files.", goal=goal)

    plan_messages = [
      {
        "role": "system",
        "content": (
          "Plan minimal code changes for Nano's codebase. "
          'Return JSON only: {"changes": [{"path": "app/...", "content": "..."}]} '
          f"with at most {settings.self_improve_max_files} files. "
          "Provide full file contents for each changed file."
        ),
      },
      {
        "role": "user",
        "content": (
          f"Goal: {goal}\n\n"
          + "\n\n".join(f"### {path}\n{content}" for path, content in file_contents.items())
        ),
      },
    ]
    raw_plan = cast(str, client.complete(messages=plan_messages)).strip()
    plan = extract_json(raw_plan)
    if not isinstance(plan, dict):
      return SelfImproveResult(
        ok=False,
        step="plan",
        error="Could not parse change plan from the model.",
        goal=goal,
      )
    changes = plan.get("changes", [])
    if not isinstance(changes, list) or not changes:
      return SelfImproveResult(ok=False, step="plan", error="No changes planned.", goal=goal)

    changed_files: list[str] = []
    for item in changes[: settings.self_improve_max_files]:
      if not isinstance(item, dict):
        continue
      path = str(item.get("path", ""))
      content = str(item.get("content", ""))
      if not path.startswith(allowed.rstrip("/")):
        continue
      write_text_file(path, content)
      changed_files.append(path)

    if not changed_files:
      return SelfImproveResult(ok=False, step="apply", error="No valid file writes.", goal=goal)

    activity.working(
      title=VERIFYING_SELF_IMPROVE_TITLE,
      detail="Running tests before opening a pull request.",
      source="tools.self_improve_service",
    )
    verify = run_pr_verification()
    if not verify.ok:
      return SelfImproveResult(
        ok=False,
        step="verify",
        changed_files=changed_files,
        error=verify.error or "Verification failed.",
        goal=goal,
      )

    pr_result = PullRequestService().run(client=client)
    if not pr_result.ok:
      return SelfImproveResult(
        ok=False,
        step=pr_result.step,
        changed_files=changed_files,
        error=pr_result.error,
        goal=goal,
      )

    return SelfImproveResult(
      ok=True,
      step="complete",
      changed_files=changed_files,
      pr_url=pr_result.url,
      goal=goal,
    )
