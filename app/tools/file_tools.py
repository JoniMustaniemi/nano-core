from __future__ import annotations

import subprocess
import sys
from typing import Any

from app.tools.base import ToolSpec
from app.tools.files import list_files, read_text_file, workspace_root, write_text_file
from app.tools.registry import register_tool


def _run_python(args: dict[str, Any]) -> str:
    """
    Run python.

    Args:
        args: Tool argument dictionary.

    Returns:
        Generated or formatted string value.
    """
    code = str(args.get("code", ""))
    timeout_seconds = int(args.get("timeout_seconds", 30))
    process = subprocess.run(
        [sys.executable, "-c", code],
        cwd=workspace_root(),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    return _format_process_output(process.returncode, process.stdout, process.stderr)


def _read_file(args: dict[str, Any]) -> str:
    """
    Read file.

    Args:
        args: Tool argument dictionary.

    Returns:
        Generated or formatted string value.
    """
    return read_text_file(str(args.get("path", "")))


def _write_file(args: dict[str, Any]) -> str:
    """
    Write file.

    Args:
        args: Tool argument dictionary.

    Returns:
        Generated or formatted string value.
    """
    return write_text_file(str(args.get("path", "")), str(args.get("content", "")))


def _list_files(args: dict[str, Any]) -> str:
    """
    List files.

    Args:
        args: Tool argument dictionary.

    Returns:
        Generated or formatted string value.
    """
    raw_path = str(args.get("path", "."))
    entries = list_files(raw_path)
    if not entries:
        return f"{raw_path} is empty or does not exist"
    return "\n".join(entries)


def _format_process_output(returncode: int, stdout: str, stderr: str) -> str:
    """
    Format process output.

    Args:
        returncode: Process exit code.
        stdout: Captured process standard output.
        stderr: Captured process standard error.

    Returns:
        Generated or formatted string value.
    """
    parts = [f"exit code: {returncode}"]
    if stdout.strip():
        parts.append(f"stdout:\n{stdout.strip()}")
    if stderr.strip():
        parts.append(f"stderr:\n{stderr.strip()}")
    return "\n".join(parts)


register_tool(
    ToolSpec(
        name="run_python",
        description="execute local Python code and return stdout/stderr.",
        args_schema={
            "code": "Python source to execute in the workspace.",
            "timeout_seconds": "Optional timeout in seconds.",
        },
        handler=_run_python,
    )
)

register_tool(
    ToolSpec(
        name="read_file",
        description="read a text file under the workspace root.",
        args_schema={"path": "Path relative to the workspace root."},
        handler=_read_file,
    )
)

register_tool(
    ToolSpec(
        name="write_file",
        description="write a text file under the workspace root.",
        args_schema={
            "path": "Path relative to the workspace root.",
            "content": "Full file contents to write.",
        },
        handler=_write_file,
    )
)

register_tool(
    ToolSpec(
        name="list_files",
        description="list files under the workspace root.",
        args_schema={"path": "Optional directory path relative to the workspace root."},
        handler=_list_files,
    )
)
