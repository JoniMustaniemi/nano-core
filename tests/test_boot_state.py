from __future__ import annotations

import pytest

from app.config import get_settings
from app.runtime.boot_state import boot_store
from app.runtime.snapshot import build_runtime_snapshot
from app.system.reboot import schedule_reboot


def test_boot_store_record_boot_is_stable_within_session() -> None:
    boot_store.reset()
    boot_store.record_boot()

    first = boot_store.snapshot()
    second = boot_store.snapshot()

    assert first.id == second.id
    assert first.id.startswith("boot_")
    assert first.booted_at == second.booted_at
    assert first.reboot_pending is False


def test_build_runtime_snapshot_includes_boot() -> None:
    boot_store.reset()
    boot_store.record_boot()

    snapshot = build_runtime_snapshot()
    boot = snapshot["boot"]

    assert isinstance(boot, dict)
    assert boot["id"].startswith("boot_")
    assert boot["booted_at"]
    assert boot["reboot_pending"] is False


def test_status_endpoint_includes_boot(api_client) -> None:
    response = api_client.get("/api/status")

    assert response.status_code == 200
    boot = response.json()["boot"]
    assert boot["id"].startswith("boot_")
    assert boot["booted_at"]
    assert boot["reboot_pending"] is False


def test_schedule_reboot_marks_reboot_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REBOOT_ENABLED", "true")
    get_settings.cache_clear()
    boot_store.reset()
    boot_store.record_boot()
    monkeypatch.setattr("app.system.reboot.time.sleep", lambda _seconds: None)
    monkeypatch.setattr(
        "app.system.reboot.subprocess.run",
        lambda *args, **kwargs: type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
    )

    assert schedule_reboot(delay_seconds=0) is True
    assert boot_store.snapshot().reboot_pending is True
    get_settings.cache_clear()
