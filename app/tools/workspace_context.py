from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from app.config import get_settings

_workspace_override: ContextVar[Path | None] = ContextVar("workspace_override", default=None)


def workspace_root() -> Path:
    """
    Return the configured workspace root path.

    Returns:
        Resolved workspace root path.
    """
    return Path(get_settings().workspace_root).resolve()


def effective_workspace_root() -> Path:
    """
    Return the active workspace root, honoring any temporary override.

    Returns:
        Resolved workspace root path.
    """
    override = _workspace_override.get()
    if override is not None:
        return override.resolve()
    return workspace_root()


@contextmanager
def workspace_override(path: Path) -> Iterator[Path]:
    """
    Temporarily route file and git operations through a different workspace root.

    Args:
        path: Workspace root to use for the duration of the context.

    Yields:
        The resolved override path.
    """
    token = _workspace_override.set(path.resolve())
    try:
        yield path.resolve()
    finally:
        _workspace_override.reset(token)
