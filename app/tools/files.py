from pathlib import Path

from app.tools.workspace_context import effective_workspace_root, workspace_root

__all__ = [
    "effective_workspace_root",
    "list_files",
    "read_text_file",
    "resolve_workspace_path",
    "workspace_root",
    "write_text_file",
]


def resolve_workspace_path(raw_path: str) -> Path:
    """
    Resolve workspace path.

    Args:
        raw_path: Workspace-relative path supplied by the caller.

    Returns:
        Path result.

    Raises:
        ValueError: If the operation cannot be completed.
    """
    root = effective_workspace_root()
    path = (root / raw_path).resolve()
    if root not in path.parents and path != root:
        raise ValueError("Path must stay within the workspace root.")
    return path


def read_text_file(raw_path: str) -> str:
    """
    Read text file.

    Args:
        raw_path: Workspace-relative path supplied by the caller.

    Returns:
        Generated or formatted string value.
    """
    return resolve_workspace_path(raw_path).read_text(encoding="utf-8")


def write_text_file(raw_path: str, content: str) -> str:
    """
    Write text file.

    Args:
        raw_path: Workspace-relative path supplied by the caller.
        content: Text content to persist or return.

    Returns:
        Generated or formatted string value.
    """
    path = resolve_workspace_path(raw_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"wrote {path}"


def list_files(raw_path: str = ".") -> list[str]:
    """
    List files.

    Args:
        raw_path: Workspace-relative path supplied by the caller.

    Returns:
        List of matching records or values.
    """
    path = resolve_workspace_path(raw_path)
    if not path.exists():
        return []
    return sorted(item.name for item in path.iterdir())
