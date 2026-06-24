from types import SimpleNamespace

from app.llm.client import LocalLLMClient


class _LocalModel:
    def create_chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, object]:
        """
        Provide test support for create chat completion.

        Args:
            messages: Conversation messages to send to the model.
            temperature: Temperature value.
            max_tokens: Max tokens value.

        Returns:
            Dictionary containing the requested data.
        """
        assert messages[-1]["content"] == "hi"
        assert temperature == 0.7
        assert max_tokens == 512
        return {"choices": [{"message": {"content": "hello from local model"}}]}


def test_llm_client_uses_local_gguf_model(monkeypatch) -> None:
    """
    Verify that llm client uses local gguf model.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.
    """
    client = LocalLLMClient()

    monkeypatch.setattr(
        "app.llm.client.get_settings",
        lambda: SimpleNamespace(
            llm_provider="local",
            llm_model_path="./models/nano.gguf",
            llm_context_size=4096,
            llm_max_tokens=512,
            llm_temperature=0.7,
            llm_base_url="http://localhost:11434",
            llm_model="test-model",
            llm_timeout_seconds=30,
        ),
    )
    monkeypatch.setattr(
        "app.llm.client._load_local_model",
        lambda path, context_size: _LocalModel(),
    )

    content = client.complete([{"role": "user", "content": "hi"}])

    assert content == "hello from local model"


def test_llm_client_auto_falls_back_when_no_local_model(monkeypatch) -> None:
    """
    Verify that llm client auto falls back when no local model.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.
    """
    client = LocalLLMClient()

    monkeypatch.setattr(
        "app.llm.client.get_settings",
        lambda: SimpleNamespace(
            llm_provider="auto",
            llm_model_path="",
            llm_context_size=4096,
            llm_max_tokens=512,
            llm_temperature=0.7,
            llm_base_url="http://localhost:11434",
            llm_model="test-model",
            llm_timeout_seconds=30,
        ),
    )
    monkeypatch.setattr(
        "app.llm.client.LocalLLMClient._complete_ollama",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.llm.client.LocalLLMClient._complete_llama_cpp_server",
        lambda *args, **kwargs: None,
    )

    content = client.complete([{"role": "user", "content": "hi"}])

    assert "Local LLM is not available yet" in content
