from types import SimpleNamespace

from app.llm.client import LocalLLMClient


class _LocalModel:
    def __init__(self) -> None:
        self.last_max_tokens: int | None = None
        self.last_temperature: float | None = None

    def create_chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, object]:
        self.last_max_tokens = max_tokens
        self.last_temperature = temperature
        assert messages[-1]["content"] == "hi"
        return {"choices": [{"message": {"content": "hello from local model"}}]}


def test_llm_client_uses_local_gguf_model(monkeypatch) -> None:
    client = LocalLLMClient()
    model = _LocalModel()

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
        lambda path, context_size: model,
    )

    content = client.complete([{"role": "user", "content": "hi"}])

    assert content == "hello from local model"
    assert model.last_max_tokens == 512
    assert model.last_temperature == 0.7


def test_llm_client_complete_overrides_max_tokens_and_temperature(monkeypatch) -> None:
    client = LocalLLMClient()
    model = _LocalModel()

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
        lambda path, context_size: model,
    )

    client.complete(
        [{"role": "user", "content": "hi"}],
        max_tokens=2048,
        temperature=0.1,
    )

    assert model.last_max_tokens == 2048
    assert model.last_temperature == 0.1


def test_llm_client_ollama_payload_includes_num_predict(monkeypatch) -> None:
    client = LocalLLMClient()
    captured: dict[str, object] = {}

    def fake_post(_self, path, payload, *, raise_on_error):
        captured["path"] = path
        captured["payload"] = payload
        return SimpleNamespace(
            json=lambda: {"message": {"content": "hello from ollama"}},
        )

    monkeypatch.setattr(
        "app.llm.client.get_settings",
        lambda: SimpleNamespace(
            llm_provider="ollama",
            llm_model_path="",
            llm_context_size=4096,
            llm_max_tokens=512,
            llm_temperature=0.7,
            llm_base_url="http://localhost:11434",
            llm_model="test-model",
            llm_timeout_seconds=30,
        ),
    )
    monkeypatch.setattr("app.llm.client.LocalLLMClient._post", fake_post)

    content = client.complete(
        [{"role": "user", "content": "hi"}],
        max_tokens=2048,
        temperature=0.1,
    )

    assert content == "hello from ollama"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    options = payload["options"]
    assert options["num_predict"] == 2048
    assert options["temperature"] == 0.1


def test_llm_client_auto_falls_back_when_no_local_model(monkeypatch) -> None:
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
