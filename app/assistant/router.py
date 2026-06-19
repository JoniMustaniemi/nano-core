from app.llm.client import LocalLLMClient


def get_llm_client() -> LocalLLMClient:
    return LocalLLMClient()
