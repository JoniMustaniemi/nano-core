from __future__ import annotations

import shlex
import subprocess
import sys
from dataclasses import dataclass

from app.config import get_settings
from app.tools.files import workspace_root


@dataclass(frozen=True, slots=True)
class VerifyResult:
    ok: bool
    command: list[str]
    exit_code: int
    output: str
    error: str | None = None


def resolve_verify_command() -> list[str] | None:
    """
    Resolve the verification command for the current workspace.

    Returns:
        Command argv list, or None when no command can be resolved.
    """
    settings = get_settings()
    if settings.github_pr_verify_command.strip():
        return _split_command(settings.github_pr_verify_command.strip())

    root = workspace_root()
    pyproject = root / "pyproject.toml"
    if pyproject.exists() and _pyproject_has_pytest(pyproject.read_text(encoding="utf-8")):
        return [sys.executable, "-m", "pytest", "-q"]

    package_json = root / "package.json"
    if package_json.exists():
        text = package_json.read_text(encoding="utf-8")
        if '"test"' in text and '"scripts"' in text:
            return ["npm", "test"]

    makefile = root / "Makefile"
    if makefile.exists() and _makefile_has_test_target(makefile.read_text(encoding="utf-8")):
        return ["make", "test"]

    return None


def run_pr_verification() -> VerifyResult:
    """
    Run the resolved verification command in the workspace.

    Returns:
        Verification result with captured output.
    """
    command = resolve_verify_command()
    if command is None:
        return VerifyResult(
            ok=False,
            command=[],
            exit_code=1,
            output="",
            error="No verification command found — set GITHUB_PR_VERIFY_COMMAND in .env",
        )

    settings = get_settings()
    try:
        process = subprocess.run(
            command,
            cwd=workspace_root(),
            capture_output=True,
            text=True,
            timeout=settings.github_pr_verify_timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        output = _truncate_output(_combine_output(exc.stdout, exc.stderr))
        return VerifyResult(
            ok=False,
            command=command,
            exit_code=124,
            output=output,
            error="Verification timed out.",
        )

    output = _truncate_output(_combine_output(process.stdout, process.stderr))
    return VerifyResult(
        ok=process.returncode == 0,
        command=command,
        exit_code=process.returncode,
        output=output,
        error=None if process.returncode == 0 else "Verification failed.",
    )


def command_display(command: list[str]) -> str:
    """
    Render a command list for display.

    Args:
        command: Command argv list.

    Returns:
        Shell-quoted command string.
    """
    return " ".join(shlex.quote(part) for part in command)


def _split_command(command: str) -> list[str]:
    return shlex.split(command, posix=False)


def _pyproject_has_pytest(text: str) -> bool:
    lowered = text.lower()
    return "[tool.pytest" in lowered or "pytest" in lowered


def _makefile_has_test_target(text: str) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("test:") or stripped.startswith(".PHONY: test"):
            return True
    return False


def _combine_output(stdout: str | None, stderr: str | None) -> str:
    parts: list[str] = []
    if stdout and stdout.strip():
        parts.append(stdout.strip())
    if stderr and stderr.strip():
        parts.append(stderr.strip())
    return "\n".join(parts)


def _truncate_output(output: str, max_chars: int = 2048) -> str:
    if len(output) <= max_chars:
        return output
    return output[-max_chars:]
