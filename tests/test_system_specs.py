from pathlib import Path
from subprocess import CompletedProcess

import pytest

from app.system.specs import (
    _probe_cpu_temperature_sysfs,
    _probe_cpu_temperature_vcgencmd,
    _probe_cpu_throttled_vcgencmd,
    collect_system_specs,
    estimate_max_context_tokens,
    format_bytes,
    format_system_analysis_report,
    probe_cpu_temperature,
    probe_memory,
    serialize_system_metrics,
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


def test_format_system_analysis_report_is_human_readable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_model = tmp_path / "chat.gguf"
    chat_model.write_bytes(b"x" * 500_000_000)
    monkeypatch.setattr(
        "app.system.specs.get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "app_name": "nano",
                "llm_provider": "local",
                "llm_model_path": str(chat_model),
                "llm_context_size": 32768,
            },
        )(),
    )

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


def test_probe_cpu_temperature_from_sysfs(tmp_path: Path) -> None:
    thermal = tmp_path / "temp"
    thermal.write_text("45200\n", encoding="utf-8")

    assert _probe_cpu_temperature_sysfs(thermal) == 45.2


def test_probe_cpu_temperature_from_vcgencmd(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.system.specs.shutil.which", lambda cmd: "/usr/bin/vcgencmd")
    monkeypatch.setattr(
        "app.system.specs.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="temp=45.2'C\n",
            stderr="",
        ),
    )

    assert _probe_cpu_temperature_vcgencmd() == 45.2


def test_probe_cpu_throttled_from_vcgencmd(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.system.specs.shutil.which", lambda cmd: "/usr/bin/vcgencmd")
    monkeypatch.setattr(
        "app.system.specs.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="throttled=0x4\n",
            stderr="",
        ),
    )

    assert _probe_cpu_throttled_vcgencmd() is True


def test_probe_cpu_temperature_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing"
    monkeypatch.setattr("app.system.specs._THERMAL_ZONE_PATH", missing)
    monkeypatch.setattr("app.system.specs.shutil.which", lambda cmd: None)

    assert probe_cpu_temperature() is None
    assert serialize_system_metrics() == {
        "cpu_temperature_celsius": None,
        "throttled": None,
    }
