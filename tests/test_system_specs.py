from pathlib import Path

from app.system.specs import (
    collect_system_specs,
    estimate_max_context_tokens,
    format_bytes,
    format_system_analysis_report,
    probe_memory,
)


def test_probe_memory_returns_values_or_none() -> None:
    memory = probe_memory()
    if memory.total_bytes is not None:
        assert memory.total_bytes > 0
    if memory.available_bytes is not None:
        assert memory.available_bytes > 0


def test_estimate_max_context_tokens_accounts_for_model_size(tmp_path: Path) -> None:
    model_path = tmp_path / "model.gguf"
    model_path.write_bytes(b"x" * 2_000_000_000)
    cap = estimate_max_context_tokens(
        str(model_path),
        available_bytes=4_000_000_000,
        reserve_bytes=1_000_000_000,
        kv_bytes_per_token=131_072,
    )
    assert cap is not None
    assert cap < 20_000


def test_collect_system_specs_includes_llm_fields() -> None:
    specs = collect_system_specs()
    assert "memory" in specs
    assert "llm" in specs
    assert "configured_chat_context" in specs["llm"]


def test_format_system_analysis_report_is_human_readable() -> None:
    report = format_system_analysis_report()
    assert "Here's how I'm running" in report
    assert "You have" in report
    assert "free out of" in report
    assert "model on your device" in report
    assert "memory window" in report
    assert "qwen" not in report.lower()
    assert "gguf" not in report.lower()
    assert "token" not in report.lower()
    assert "./models/" not in report


def test_format_bytes() -> None:
    assert format_bytes(1_073_741_824) == "1.0 GB"
    assert format_bytes(2048) == "2 KB"
