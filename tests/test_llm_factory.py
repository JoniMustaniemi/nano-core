import pytest

from app.llm.factory import get_llm_client


@pytest.fixture(autouse=True)
def clear_client_cache() -> None:
    get_llm_client.cache_clear()
    yield
    get_llm_client.cache_clear()


def test_get_llm_client_returns_cached_instance() -> None:
    assert get_llm_client() is get_llm_client()
