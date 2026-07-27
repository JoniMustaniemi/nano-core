from __future__ import annotations

import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

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


def resolve_mypy_command() -> list[str] | None:
    """
    Resolve the mypy command for the current workspace.

    Returns:
        Command argv list, or None when mypy is not configured.
    """
    root = effective_workspace_root()
    pyproject = root / "pyproject.toml"
    if pyproject.exists() and _pyproject_has_mypy(pyproject.read_text(encoding="utf-8")):
        return [sys.executable, "-m", "mypy", "app"]
    return None


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
    configured = str(settings.github_pr_verify_command or "").strip()
    if configured:
        return _normalize_command_interpreter(_split_command(configured))

    root = effective_workspace_root()
    pyproject = root / "pyproject.toml"
    if pyproject.exists() and _pyproject_has_pytest(pyproject.read_text(encoding="utf-8")):
        return [sys.executable, "-m", "pytest", "-q", _pytest_basetemp_arg()]

    package_json = root / "package.json"
    if package_json.exists():
        text = package_json.read_text(encoding="utf-8")
        if '"test"' in text and '"scripts"' in text:
            return ["npm", "test"]

    makefile = root / "Makefile"
    if makefile.exists() and _makefile_has_test_target(makefile.read_text(encoding="utf-8")):
        return ["make", "test"]

    return None


def resolve_ruff_format_command() -> list[str] | None:
    """
    Resolve the ruff format command for the current workspace.

    Returns:
        Command argv list, or None when ruff is not configured.
    """
    command = resolve_lint_command()
    if command is None:
        return None
    return [command[0], command[1], command[2], "format", *command[4:]]


def run_pr_lint() -> VerifyResult:
    """
    Run lint and type-check commands in the workspace.

    Runs ruff (with optional auto-fix) first, then mypy when configured.

    Returns:
        Lint result with captured output. Skipped projects return ok=True.
    """
    ruff_result = _run_ruff_lint()
    if not ruff_result.ok:
        return ruff_result

    mypy_result = _run_mypy_check()
    if not mypy_result.ok:
        return mypy_result

    if not ruff_result.command and not mypy_result.command:
        return VerifyResult(ok=True, command=[], exit_code=0, output="")

    return VerifyResult(
        ok=True,
        command=ruff_result.command or mypy_result.command,
        exit_code=0,
        output=_append_output(ruff_result.output, mypy_result.output),
        error=None,
        auto_fixed=ruff_result.auto_fixed,
    )


def _run_ruff_lint() -> VerifyResult:
    """
    Run ruff lint checks, applying auto-fix once when ruff reports fixable issues.

    Returns:
        Ruff lint result. Skipped projects return ok=True.
    """
    command = resolve_lint_command()
    if command is None:
        return VerifyResult(ok=True, command=[], exit_code=0, output="")

    result = _run_command(command, failure_message="Lint checks failed.")
    if result.ok or not _has_fixable_ruff_issues(result.output):
        return _finalize_ruff_lint(result)

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

    return _finalize_ruff_lint(
        VerifyResult(
            ok=True,
            command=command,
            exit_code=0,
            output=_append_output("Auto-fixed lint issues with ruff --fix.", recheck.output),
            error=None,
            auto_fixed=True,
        )
    )


def _finalize_ruff_lint(result: VerifyResult) -> VerifyResult:
    if not result.ok:
        return VerifyResult(
            ok=False,
            command=result.command,
            exit_code=result.exit_code,
            output=result.output,
            error=_summarize_check_failure(result.error or "Lint checks failed.", result.output),
        )

    format_result = _run_ruff_format()
    if not format_result.ok:
        return format_result

    output = _append_output(result.output, format_result.output)
    return VerifyResult(
        ok=True,
        command=result.command,
        exit_code=0,
        output=output,
        error=None,
        auto_fixed=result.auto_fixed or format_result.auto_fixed,
    )


def _run_ruff_format() -> VerifyResult:
    """
    Run ruff format so generated edits match repository style before commit.

    Returns:
        Ruff format result. Skipped projects return ok=True.
    """
    command = resolve_ruff_format_command()
    if command is None:
        return VerifyResult(ok=True, command=[], exit_code=0, output="")

    result = _run_command(command, failure_message="Format checks failed.")
    if result.ok:
        if "reformatted" in result.output.lower():
            return VerifyResult(
                ok=True,
                command=command,
                exit_code=0,
                output=_append_output("Auto-formatted files with ruff format.", result.output),
                error=None,
                auto_fixed=True,
            )
        return result

    return VerifyResult(
        ok=False,
        command=result.command,
        exit_code=result.exit_code,
        output=result.output,
        error=_summarize_check_failure(result.error or "Format checks failed.", result.output),
    )


def _run_mypy_check() -> VerifyResult:
    """
    Run mypy type checks when the workspace configures it.

    Returns:
        Mypy result with captured output. Skipped projects return ok=True.
    """
    command = resolve_mypy_command()
    if command is None:
        return VerifyResult(ok=True, command=[], exit_code=0, output="")
    result = _run_command(command, failure_message="Type checks failed.")
    if result.ok:
        return result
    return VerifyResult(
        ok=False,
        command=result.command,
        exit_code=result.exit_code,
        output=result.output,
        error=_summarize_check_failure(result.error or "Type checks failed.", result.output),
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


def _normalize_command_interpreter(command: list[str]) -> list[str]:
    if not command:
        return command
    if command[0].lower() in {"python", "python3"}:
        return [sys.executable, *command[1:]]
    return command


def _pytest_basetemp_arg() -> str:
    base = Path(tempfile.gettempdir()) / "nano-pr-pytest"
    return f"--basetemp={base}"


def _run_command(command: list[str], *, failure_message: str) -> VerifyResult:
    settings = get_settings()
    try:
        process = subprocess.run(
            command,
            cwd=effective_workspace_root(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
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


def _summarize_check_failure(message: str, output: str) -> str:
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if "error:" in lowered or lowered.startswith("error "):
            return f"{message.rstrip('.')}: {stripped}"
    tail = output.strip().splitlines()[-1].strip() if output.strip() else ""
    if tail and tail not in message:
        return f"{message.rstrip('.')}: {tail}"
    return message


def _append_output(*parts: str) -> str:
    return "\n".join(part.strip() for part in parts if part.strip())


def _pyproject_has_pytest(text: str) -> bool:
    lowered = text.lower()
    return "[tool.pytest" in lowered or "pytest" in lowered


def _pyproject_has_ruff(text: str) -> bool:
    return "[tool.ruff" in text.lower()


def _pyproject_has_mypy(text: str) -> bool:
    return "[tool.mypy" in text.lower()


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
