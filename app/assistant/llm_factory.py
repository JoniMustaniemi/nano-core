"""Backward-compatible re-export. Prefer app.llm.factory."""

from app.llm.factory import get_code_llm_client, get_llm_client

__all__ = ["get_code_llm_client", "get_llm_client"]
