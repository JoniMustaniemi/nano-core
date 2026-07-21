from __future__ import annotations


class ToolError(Exception):
    """Raised when a tool handler cannot complete the requested action."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
