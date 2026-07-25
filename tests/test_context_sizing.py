from pathlib import Path

import pytest

from app.llm.context_sizing import (
    CONTEXT_SIZE_LADDER,
    context_sizes_to_try,
    format_context_downgrade_notice,
)


def test_context_sizes_to_try_respects_ladder() -> None:
    sizes = context_sizes_to_try("./models/test.gguf", 32768)
    assert sizes == list(CONTEXT_SIZE_LADDER)


def test_context_sizes_to_try_caps_to_requested() -> None:
    sizes = context_sizes_to_try("./models/test.gguf", 4096)
    assert sizes == [4096, 2048, 1024, 512]


def test_context_sizes_to_try_uses_ram_estimate(monkeypatch, tmp_path: Path) -> None:
    model_path = tmp_path / "tiny.gguf"
    model_path.write_bytes(b"x" * 1024)

    def fake_estimate(*_args, **kwargs):
        del kwargs
        return 4096

    monkeypatch.setattr("app.llm.context_sizing.estimate_max_context_tokens", fake_estimate)
    sizes = context_sizes_to_try(str(model_path), 32768)
    assert sizes == [4096, 2048, 1024, 512]


def test_format_context_downgrade_notice() -> None:
    notice = format_context_downgrade_notice(
        "./models/chat.gguf",
        32768,
        8192,
        reason="memory",
    )
    assert "smaller memory window" in notice
    assert "free memory was too low" in notice


def test_load_local_model_downgrades_on_failure(monkeypatch, tmp_path: Path) -> None:
    from app.llm.context_sizing import load_local_model, pop_context_load_notice

    model_path = tmp_path / "model.gguf"
    model_path.write_bytes(b"x" * 16)
    attempts: list[int] = []

    class FakeLlama:
        def __init__(self, model_path: str, n_ctx: int, verbose: bool = False) -> None:
            del model_path, verbose
            attempts.append(n_ctx)
            if n_ctx > 4096:
                raise OSError("insufficient memory")

    monkeypatch.setattr("app.llm.context_sizing._create_llama_model", FakeLlama)
    monkeypatch.setattr(
        "app.llm.context_sizing.context_sizes_to_try",
        lambda _path, requested: [size for size in CONTEXT_SIZE_LADDER if size <= requested],
    )

    load_local_model.cache_clear()
    model = load_local_model(str(model_path), 32768)

    assert isinstance(model, FakeLlama)
    assert 32768 in attempts
    assert 4096 in attempts
    notice = pop_context_load_notice(str(model_path))
    assert notice is not None
    assert "smaller memory window" in notice.lower()


def test_load_local_model_raises_clear_error_when_all_sizes_fail(
    monkeypatch, tmp_path: Path
) -> None:
    from app.llm.context_sizing import LocalModelLoadError, load_local_model

    model_path = tmp_path / "model.gguf"
    model_path.write_bytes(b"x" * 16)

    class FailingLlama:
        def __init__(self, *_args, **_kwargs) -> None:
            raise OSError("insufficient memory")

    monkeypatch.setattr("app.llm.context_sizing._create_llama_model", FailingLlama)
    monkeypatch.setattr(
        "app.llm.context_sizing.context_sizes_to_try",
        lambda _path, requested: [512],
    )
    monkeypatch.setattr(
        "app.llm.context_sizing.probe_memory",
        lambda: __import__("app.system.specs", fromlist=["MemoryInfo"]).MemoryInfo(
            total_bytes=8_000_000_000,
            available_bytes=512_000_000,
        ),
    )

    load_local_model.cache_clear()
    with pytest.raises(LocalModelLoadError, match="could not load"):
        load_local_model(str(model_path), 32768)
