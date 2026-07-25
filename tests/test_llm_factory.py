import pytest

from app.llm.factory import _get_llm_client_for_role, get_code_llm_client, get_llm_client
from app.llm.roles import ModelRole


@pytest.fixture(autouse=True)
def clear_client_cache() -> None:
    _get_llm_client_for_role.cache_clear()
    yield
    _get_llm_client_for_role.cache_clear()


def test_get_llm_client_and_code_client_are_distinct_instances() -> None:
    chat_client = get_llm_client()
    code_client = get_code_llm_client()

    assert chat_client is not code_client


def test_get_llm_client_returns_cached_chat_instance() -> None:
    assert get_llm_client() is get_llm_client()


def test_get_code_llm_client_returns_cached_code_instance() -> None:
    assert get_code_llm_client() is get_code_llm_client()


def test_factory_clients_have_expected_roles() -> None:
    assert get_llm_client()._role == ModelRole.CHAT
    assert get_code_llm_client()._role == ModelRole.CODE
