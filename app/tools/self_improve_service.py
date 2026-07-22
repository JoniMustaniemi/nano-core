from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, cast

from app.assistant.agent_rules import extract_json
from app.config import get_settings
from app.proactive.codebase_examine import walk_app_files
from app.runtime.activity import activity
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


class SelfImproveService:
  """Orchestrated self-improvement: explore, plan, write, verify, PR."""

  def run(self, *, client: Any, goal: str) -> SelfImproveResult:
    settings = get_settings()
    allowed = settings.self_improve_allowed_prefix

    activity.working(
      title="Nano is planning self-improvement.",
      detail=goal,
      source="tools.self_improve_service",
    )

    file_index = walk_app_files(max_files=30)
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
      {"role": "user", "content": f"Goal: {goal}\n\nFile index:\n" + "\n".join(file_index)},
    ]
    raw_select = cast(str, client.complete(messages=select_messages)).strip()
    selection = extract_json(raw_select)
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
      title="Nano is verifying self-improvement.",
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
