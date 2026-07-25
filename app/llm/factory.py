from __future__ import annotations

from functools import lru_cache

from app.llm.client import LocalLLMClient
from app.llm.roles import ModelRole


@lru_cache(maxsize=2)
def _get_llm_client_for_role(role: ModelRole) -> LocalLLMClient:
    return LocalLLMClient(role=role)


def get_llm_client() -> LocalLLMClient:
    """
    Get the chat LLM client.

    Returns:
        LocalLLMClient result.
    """
    return _get_llm_client_for_role(ModelRole.CHAT)


def get_code_llm_client() -> LocalLLMClient:
    """
    Get the code LLM client.

    Returns:
        LocalLLMClient result.
    """
    return _get_llm_client_for_role(ModelRole.CODE)
