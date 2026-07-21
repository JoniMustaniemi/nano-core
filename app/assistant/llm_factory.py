from app.llm.client import LocalLLMClient


def get_llm_client() -> LocalLLMClient:
    """
    Get llm client.

    Returns:
        LocalLLMClient result.
    """
    return LocalLLMClient()
