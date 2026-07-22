from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, cast

from app.assistant.agent_rules import extract_json
from app.config import get_settings
from app.memory import codebase_index
from app.proactive.codebase_files import list_all_app_files
from app.runtime.activity import activity
from app.runtime.dev import uvicorn_reload_enabled
from app.runtime.status_copy import (
  PLANNING_SELF_IMPROVE_TITLE,
  SELF_IMPROVE_FAILED_TITLE,
  SELF_IMPROVE_RELOAD_BLOCKED_ERROR,
  VERIFYING_SELF_IMPROVE_DETAIL,
  VERIFYING_SELF_IMPROVE_TITLE,
)
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


_LLM_UNAVAILABLE_MARKERS = (
    "Local LLM is not available yet",
    "LLM_MODEL_PATH",
)
_SELECT_JSON_HINT = '{"files_to_read": ["app/..."]}'
_PLAN_JSON_HINT = '{"path": "app/...", "content": "..."}'
_PATCH_JSON_HINT = '{"path": "app/...", "old_text": "...", "new_text": "..."}'
_GOAL_FILE_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("timer", "timers"), "app/assistant/flows/timer.py"),
    (("timer", "timers", "message", "messages", "status", "wording", "clearer", "copy"), "app/runtime/status_copy.py"),
    (("wake", "greeting", "ack"), "app/runtime/status_copy.py"),
    (("note", "notes"), "app/assistant/flows/note.py"),
    (("health",), "app/health/checks.py"),
    (("pull request", "pr", "github"), "app/tools/pr_service.py"),
)


def _looks_like_llm_unavailable(raw: str) -> bool:
    return any(marker in raw for marker in _LLM_UNAVAILABLE_MARKERS)


def _complete_json_dict(
    client: Any,
    messages: list[dict[str, str]],
    *,
    correction: str,
    attempts: int = 2,
) -> dict[str, Any] | None:
    conversation = list(messages)
    for _attempt in range(attempts):
        raw = cast(str, client.complete(messages=conversation)).strip()
        if _looks_like_llm_unavailable(raw):
            return None
        payload = extract_json(raw)
        if isinstance(payload, dict):
            return payload
        conversation.extend(
            [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": correction},
            ]
        )
    return None


def _parse_selection(payload: dict[str, Any]) -> list[str]:
    files_to_read = payload.get("files_to_read", [])
    if not isinstance(files_to_read, list):
        return []
    return [str(path) for path in files_to_read if str(path).strip()]


def _fallback_files_for_goal(goal: str, *, allowed: str) -> list[str]:
    lowered = goal.lower()
    allowed_prefix = allowed.rstrip("/")
    matched: list[str] = []
    for keywords, path in _GOAL_FILE_HINTS:
        if any(keyword in lowered for keyword in keywords):
            if path.startswith(allowed_prefix) and path not in matched:
                matched.append(path)
    return matched


def _parse_patch_change(
    payload: dict[str, Any],
    *,
    expected_path: str,
    allowed: str,
    original_content: str,
) -> dict[str, str] | None:
    parsed = _parse_single_file_change(
        payload,
        expected_path=expected_path,
        allowed=allowed,
    )
    if parsed is not None:
        return parsed

    allowed_prefix = allowed.rstrip("/")
    path = str(payload.get("path", "")).strip()
    old_text = str(payload.get("old_text", payload.get("search", "")))
    new_text = str(payload.get("new_text", payload.get("replace", "")))
    if not path or path != expected_path or not path.startswith(allowed_prefix):
        return None
    if not old_text or old_text not in original_content:
        return None
    return {
        "path": path,
        "content": original_content.replace(old_text, new_text, 1),
    }


def _parse_single_file_change(
    payload: dict[str, Any],
    *,
    expected_path: str,
    allowed: str,
) -> dict[str, str] | None:
    allowed_prefix = allowed.rstrip("/")
    path = str(payload.get("path", "")).strip()
    content = str(payload.get("content", ""))
    if path and content and path.startswith(allowed_prefix):
        return {"path": path, "content": content}

    changes = payload.get("changes")
    if isinstance(changes, list):
        for item in changes:
            if not isinstance(item, dict):
                continue
            item_path = str(item.get("path", "")).strip()
            item_content = str(item.get("content", ""))
            if item_path == expected_path and item_content and item_path.startswith(allowed_prefix):
                return {"path": item_path, "content": item_content}
    return None


def _plan_single_file_change(
    client: Any,
    *,
    goal: str,
    path: str,
    content: str,
    allowed: str,
) -> dict[str, str] | None:
    patch_messages = [
        {
            "role": "system",
            "content": (
                "You edit one Python source file for a self-improvement task. "
                f"Return JSON only: {_PATCH_JSON_HINT} "
                "Use old_text copied exactly from the file and new_text as the replacement. "
                "Keep the JSON small. No markdown fences."
            ),
        },
        {
            "role": "user",
            "content": f"Goal: {goal}\n\n### {path}\n{content}",
        },
    ]
    patch_correction = (
        "Your previous response was invalid. Return JSON only with path, old_text, and new_text. "
        f"Example: {_PATCH_JSON_HINT}"
    )
    for _attempt in range(3):
        raw = cast(str, client.complete(messages=patch_messages)).strip()
        if _looks_like_llm_unavailable(raw):
            return None
        payload = extract_json(raw)
        if isinstance(payload, dict):
            parsed = _parse_patch_change(
                payload,
                expected_path=path,
                allowed=allowed,
                original_content=content,
            )
            if parsed is not None:
                return parsed
        patch_messages.extend(
            [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": patch_correction},
            ]
        )

    full_messages = [
        {
            "role": "system",
            "content": (
                "You edit one Python source file for a self-improvement task. "
                f"Return JSON only: {_PLAN_JSON_HINT} "
                "where content is the complete updated file. "
                "Use \\n for newlines inside the JSON string. No markdown fences."
            ),
        },
        {
            "role": "user",
            "content": f"Goal: {goal}\n\n### {path}\n{content}",
        },
    ]
    full_correction = (
        "Your previous response was invalid. Return JSON only with keys path and content. "
        f"Example: {_PLAN_JSON_HINT}"
    )
    for _attempt in range(2):
        raw = cast(str, client.complete(messages=full_messages)).strip()
        if _looks_like_llm_unavailable(raw):
            return None
        payload = extract_json(raw)
        if isinstance(payload, dict):
            parsed = _parse_single_file_change(
                payload,
                expected_path=path,
                allowed=allowed,
            )
            if parsed is not None:
                return parsed
        full_messages.extend(
            [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": full_correction},
            ]
        )
    return None


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


def _fail_self_improve(
  *,
  step: str,
  error: str,
  goal: str,
  changed_files: list[str] | None = None,
) -> SelfImproveResult:
  activity.error(
    title=SELF_IMPROVE_FAILED_TITLE,
    detail=error,
    source="tools.self_improve_service",
  )
  return SelfImproveResult(
    ok=False,
    step=step,
    error=error,
    goal=goal,
    changed_files=changed_files,
  )


class SelfImproveService:
  """Orchestrated self-improvement: explore, plan, write, verify, PR."""

  def run(self, *, client: Any, goal: str) -> SelfImproveResult:
    if uvicorn_reload_enabled():
      return _fail_self_improve(
        step="preflight",
        error=SELF_IMPROVE_RELOAD_BLOCKED_ERROR,
        goal=goal,
      )

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
          f"Return JSON only: {_SELECT_JSON_HINT} with at most "
          f"{settings.self_improve_max_files} paths. No markdown fences."
        ),
      },
      {
        "role": "user",
        "content": (
          f"Goal: {goal}\n\nKnown files:\n" + "\n".join(selection_lines)
        ),
      },
    ]
    selection = _complete_json_dict(
      client,
      select_messages,
      correction=(
        "Your previous response was invalid. Return JSON only with key files_to_read. "
        f"Example: {_SELECT_JSON_HINT}"
      ),
    )
    files_to_read = _parse_selection(selection) if selection is not None else []
    if not files_to_read:
      files_to_read = _fallback_files_for_goal(goal, allowed=allowed)
    if selection is None and not files_to_read:
      return _fail_self_improve(
        step="select",
        error="Could not parse file selection from the model.",
        goal=goal,
      )
    if not files_to_read:
      return _fail_self_improve(step="select", error="No files selected.", goal=goal)

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
      return _fail_self_improve(
        step="read",
        error="Could not read target files.",
        goal=goal,
      )

    changed_files: list[str] = []
    for path, content in file_contents.items():
      planned = _plan_single_file_change(
        client,
        goal=goal,
        path=path,
        content=content,
        allowed=allowed,
      )
      if planned is None:
        return _fail_self_improve(
          step="plan",
          error=f"Could not parse change plan from the model for {path}.",
          goal=goal,
        )
      write_text_file(planned["path"], planned["content"])
      changed_files.append(planned["path"])

    if not changed_files:
      return _fail_self_improve(step="plan", error="No changes planned.", goal=goal)

    activity.working(
      title=VERIFYING_SELF_IMPROVE_TITLE,
      detail=VERIFYING_SELF_IMPROVE_DETAIL,
      source="tools.self_improve_service",
    )
    verify = run_pr_verification()
    if not verify.ok:
      return _fail_self_improve(
        step="verify",
        error=verify.error or "Verification failed.",
        goal=goal,
        changed_files=changed_files,
      )

    pr_result = PullRequestService().run(client=client)
    if not pr_result.ok:
      return _fail_self_improve(
        step=pr_result.step,
        error=pr_result.error or "Pull request failed.",
        goal=goal,
        changed_files=changed_files,
      )

    return SelfImproveResult(
      ok=True,
      step="complete",
      changed_files=changed_files,
      pr_url=pr_result.url,
      goal=goal,
    )
