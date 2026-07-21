"""Backward-compatible re-exports for assistant routing rules."""

from app.assistant.rules import *  # noqa: F403
from app.assistant.rules import __all__ as _RULES_ALL

__all__ = list(_RULES_ALL)
