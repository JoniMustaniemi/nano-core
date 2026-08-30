from __future__ import annotations

from functools import lru_cache

from app.llm.client import LocalLLMClient


@lru_cache(maxsize=1)
def get_llm_client() -> LocalLLMClient:
    """
    Get the chat LLM client.

    Returns:
        LocalLLMClient result.
    """
    return LocalLLMClient()
