#!/usr/bin/env python3
"""Run the full local validation suite (mirrors CI)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run(command: list[str]) -> None:
    print(f"+ {' '.join(command)}", flush=True)
    result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1])
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> None:
    run(["ruff", "check", "app", "tests"])
    run(["ruff", "format", "--check", "app", "tests"])
    run(["mypy", "app"])
    run(["pytest"])


if __name__ == "__main__":
    main()
