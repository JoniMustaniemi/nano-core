from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from app.assistant.agent_rules import extract_json
from app.config import get_settings
from app.proactive.types import ProactiveOffer
from app.tools.files import read_text_file, workspace_root


def walk_app_files(*, max_files: int = 40) -> list[str]:
  root = workspace_root() / "app"
  if not root.exists():
    return []
  paths: list[str] = []
  for dirpath, dirnames, filenames in os.walk(root):
    dirnames.sort()
    for name in sorted(filenames):
      if not name.endswith(".py"):
        continue
      full = Path(dirpath) / name
      rel = full.relative_to(workspace_root()).as_posix()
      paths.append(rel)
      if len(paths) >= max_files:
        return paths
  return paths


class CodebaseExamineService:
  """Read-only codebase analysis that may produce proactive suggestions."""

  def run(self, *, client: Any) -> ProactiveOffer | None:
    settings = get_settings()
    if not settings.idle_examine_enabled:
      return None

    file_index = walk_app_files()
    if not file_index:
      return None

    select_messages = [
      {
        "role": "system",
        "content": (
          "You review Nano's Python source for small improvements. "
          "Return JSON only: {\"files_to_read\": [\"app/...\"]} with at most 3 paths."
        ),
      },
      {
        "role": "user",
        "content": "File index:\n" + "\n".join(file_index),
      },
    ]
    raw_select = cast(str, client.complete(messages=select_messages)).strip()
    selection = extract_json(raw_select)
    files_to_read = selection.get("files_to_read", [])
    if not isinstance(files_to_read, list):
      return None

    contents: list[str] = []
    for raw_path in files_to_read[:3]:
      path = str(raw_path)
      if not path.startswith(settings.self_improve_allowed_prefix.rstrip("/")):
        continue
      try:
        text = read_text_file(path)
      except (OSError, ValueError):
        continue
      if len(text) > settings.self_improve_max_file_chars:
        text = text[: settings.self_improve_max_file_chars]
      contents.append(f"### {path}\n{text}")

    if not contents:
      return None

    suggest_messages = [
      {
        "role": "system",
        "content": (
          "Suggest one small self-improvement for Nano's codebase. "
          "Return JSON only: "
          '{"suggestion": "...", "goal": "...", "confidence": "low|medium|high"} '
          'or {"suggestion": null}.'
        ),
      },
      {
        "role": "user",
        "content": "\n\n".join(contents),
      },
    ]
    raw_suggest = cast(str, client.complete(messages=suggest_messages)).strip()
    suggestion_payload = extract_json(raw_suggest)
    suggestion = suggestion_payload.get("suggestion")
    if not suggestion:
      return None

    confidence = str(suggestion_payload.get("confidence", "low")).lower()
    if confidence == "low":
      return None

    goal = str(suggestion_payload.get("goal", suggestion)).strip()
    summary = str(suggestion).strip()
    return ProactiveOffer(
      kind="self_improvement_suggestion",
      title="Codebase improvement idea",
      summary=summary,
      payload={"goal": goal, "files": [str(p) for p in files_to_read[:3]]},
      created_at=datetime.now(UTC),
    )
