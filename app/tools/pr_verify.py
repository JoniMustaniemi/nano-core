from __future__ import annotations

import shlex
import subprocess
import sys
from dataclasses import dataclass

from app.config import get_settings
from app.tools.workspace_context import effective_workspace_root


@dataclass(frozen=True, slots=True)
class VerifyResult:
    ok: bool
    command: list[str]
    exit_code: int
    output: str
    error: str | None = None
    auto_fixed: bool = False


def resolve_lint_command() -> list[str] | None:
    """
    Resolve the lint command for the current workspace.

    Returns:
        Command argv list, or None when no lint command can be resolved.
    """
    root = effective_workspace_root()
    pyproject = root / "pyproject.toml"
    if pyproject.exists() and _pyproject_has_ruff(pyproject.read_text(encoding="utf-8")):
        return [sys.executable, "-m", "ruff", "check", "app", "tests"]
    return None


def resolve_verify_command() -> list[str] | None:
    """
    Resolve the verification command for the current workspace.

    Returns:
        Command argv list, or None when no command can be resolved.
    """
    settings = get_settings()
    if settings.github_pr_verify_command.strip():
        return _split_command(settings.github_pr_verify_command.strip())

    root = effective_workspace_root()
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


def run_pr_lint() -> VerifyResult:
    """
    Run the resolved lint command in the workspace.

    When ruff reports fixable issues, applies ``--fix`` and re-checks once.

    Returns:
        Lint result with captured output. Skipped projects return ok=True.
    """
    command = resolve_lint_command()
    if command is None:
        return VerifyResult(ok=True, command=[], exit_code=0, output="")

    result = _run_command(command, failure_message="Lint checks failed.")
    if result.ok or not _has_fixable_ruff_issues(result.output):
        return result

    fix_command = [*command, "--fix"]
    fix_result = _run_command(fix_command, failure_message="Lint auto-fix failed.")
    if not fix_result.ok:
        return VerifyResult(
            ok=False,
            command=fix_command,
            exit_code=fix_result.exit_code,
            output=_append_output(result.output, fix_result.output),
            error="Lint auto-fix failed.",
        )

    recheck = _run_command(command, failure_message="Lint checks failed.")
    if not recheck.ok:
        return recheck

    return VerifyResult(
        ok=True,
        command=command,
        exit_code=0,
        output=_append_output("Auto-fixed lint issues with ruff --fix.", recheck.output),
        error=None,
        auto_fixed=True,
    )


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
    return _run_command(command, failure_message="Verification failed.")


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


def _run_command(command: list[str], *, failure_message: str) -> VerifyResult:
    settings = get_settings()
    try:
        process = subprocess.run(
            command,
            cwd=effective_workspace_root(),
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
            error=f"{failure_message.rstrip('.')} timed out.",
        )

    output = _truncate_output(_combine_output(process.stdout, process.stderr))
    return VerifyResult(
        ok=process.returncode == 0,
        command=command,
        exit_code=process.returncode,
        output=output,
        error=None if process.returncode == 0 else failure_message,
    )


def _has_fixable_ruff_issues(output: str) -> bool:
    if not output:
        return False
    lowered = output.lower()
    if "fixable with the `--fix` option" in lowered:
        return True
    if "fixable with the --fix option" in lowered:
        return True
    return "[*]" in output


def _append_output(*parts: str) -> str:
    return "\n".join(part.strip() for part in parts if part.strip())


def _pyproject_has_pytest(text: str) -> bool:
    lowered = text.lower()
    return "[tool.pytest" in lowered or "pytest" in lowered


def _pyproject_has_ruff(text: str) -> bool:
    return "[tool.ruff" in text.lower()


def _makefile_has_test_target(text: str) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("test:") or stripped.startswith(".PHONY: test"):
            return True
    return False


def _combine_output(stdout: str | bytes | None, stderr: str | bytes | None) -> str:
    parts: list[str] = []
    for value in (stdout, stderr):
        text = _output_text(value)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _output_text(value: str | bytes | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip() or None
    stripped = value.strip()
    return stripped or None


def _truncate_output(output: str, max_chars: int = 2048) -> str:
    if len(output) <= max_chars:
        return output
    return output[-max_chars:]
