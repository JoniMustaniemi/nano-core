#!/usr/bin/env python3
"""Auto-bump patch version in pyproject.toml when committing code changes."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
VERSION_PATTERN = re.compile(r'(^version\s*=\s*")([^"]+)(")', re.MULTILINE)

DOCS_ONLY_SUFFIXES = (".md",)


def run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def get_staged_files() -> list[str]:
    result = run_git("diff", "--cached", "--name-only", "--diff-filter=ACMR")
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def is_docs_only_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    name = Path(normalized).name
    if name == "pyproject.toml":
        return True
    return normalized.endswith(DOCS_ONLY_SUFFIXES)


def has_code_changes(staged_files: list[str]) -> bool:
    code_files = [path for path in staged_files if not is_docs_only_path(path)]
    return bool(code_files)


def read_version(content: str) -> str:
    match = VERSION_PATTERN.search(content)
    if match is None:
        raise ValueError("Could not find [project].version in pyproject.toml")
    return match.group(2)


def write_version(content: str, version: str) -> str:
    updated, count = VERSION_PATTERN.subn(rf'\g<1>{version}\g<3>', content, count=1)
    if count != 1:
        raise ValueError("Could not update [project].version in pyproject.toml")
    return updated


def bump_patch(version: str) -> str:
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"Unsupported version format: {version}")
    major, minor, patch = (int(part) for part in parts)
    return f"{major}.{minor}.{patch + 1}"


def read_head_version() -> str | None:
    result = run_git("show", "HEAD:pyproject.toml")
    if result.returncode != 0:
        return None
    return read_version(result.stdout)


def stage_pyproject() -> None:
    result = run_git("add", "pyproject.toml")
    if result.returncode != 0:
        print(result.stderr.strip() or "Failed to stage pyproject.toml", file=sys.stderr)
        raise SystemExit(result.returncode)


def main() -> None:
    staged_files = get_staged_files()
    if not staged_files or not has_code_changes(staged_files):
        return

    if not PYPROJECT.exists():
        print("pyproject.toml not found", file=sys.stderr)
        raise SystemExit(1)

    content = PYPROJECT.read_text(encoding="utf-8")
    current_version = read_version(content)
    head_version = read_head_version()

    if head_version is None:
        head_version = current_version

    if current_version != head_version:
        stage_pyproject()
        print(f"Version already bumped: {head_version} -> {current_version}")
        return

    new_version = bump_patch(head_version)
    PYPROJECT.write_text(write_version(content, new_version), encoding="utf-8")
    stage_pyproject()
    print(f"Bumped version: {head_version} -> {new_version}")


if __name__ == "__main__":
    main()
