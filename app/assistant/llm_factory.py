"""Backward-compatible re-export. Prefer app.llm.factory."""

from app.llm.factory import get_llm_client

__all__ = ["get_llm_client"]
