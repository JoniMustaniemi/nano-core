from unittest.mock import MagicMock

import pytest

from app.config import get_settings
from app.system.reboot import schedule_service_restart


def test_schedule_service_restart_skipped_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERVICE_RESTART_ENABLED", "false")
    get_settings.cache_clear()

    assert schedule_service_restart() is False
    get_settings.cache_clear()


def test_schedule_service_restart_runs_systemctl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERVICE_RESTART_ENABLED", "true")
    get_settings.cache_clear()
    monkeypatch.setattr("app.system.reboot.time.sleep", lambda _seconds: None)

    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(args)
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("app.system.reboot.subprocess.run", fake_run)

    assert schedule_service_restart(delay_seconds=0) is True

    import time

    deadline = time.time() + 2.0
    while not calls and time.time() < deadline:
        time.sleep(0.01)

    assert calls == [["sudo", "/bin/systemctl", "restart", "nano-core"]]
    get_settings.cache_clear()


def test_schedule_service_restart_uses_custom_unit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERVICE_RESTART_ENABLED", "true")
    monkeypatch.setenv("SERVICE_UNIT_NAME", "nano-core-test")
    get_settings.cache_clear()
    monkeypatch.setattr("app.system.reboot.time.sleep", lambda _seconds: None)

    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(args)
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("app.system.reboot.subprocess.run", fake_run)

    assert schedule_service_restart(delay_seconds=0) is True

    import time

    deadline = time.time() + 2.0
    while not calls and time.time() < deadline:
        time.sleep(0.01)

    assert calls == [["sudo", "/bin/systemctl", "restart", "nano-core-test"]]
    get_settings.cache_clear()
