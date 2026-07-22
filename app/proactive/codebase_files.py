from __future__ import annotations

import hashlib
import os
from pathlib import Path

from app.tools.files import read_text_file, workspace_root


def list_all_app_files() -> list[str]:
  """Return every app/**/*.py path relative to the workspace root."""
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
      paths.append(full.relative_to(workspace_root()).as_posix())
  return paths


def walk_app_files(*, max_files: int = 40) -> list[str]:
  """Return up to max_files from list_all_app_files (legacy helper)."""
  return list_all_app_files()[:max_files]


def package_for_path(path: str) -> str:
  """Return the parent directory for a workspace-relative path."""
  parent = Path(path).parent.as_posix()
  return parent or "app"


def file_content_hash(path: str) -> str:
  """Return a SHA-256 hex digest of the file bytes."""
  data = read_text_file(path).encode("utf-8")
  return hashlib.sha256(data).hexdigest()
