from unittest.mock import MagicMock

import pytest

from app.config import get_settings
from app.system.reboot import schedule_reboot


def test_schedule_reboot_skipped_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REBOOT_ENABLED", "false")
    get_settings.cache_clear()

    assert schedule_reboot() is False
    get_settings.cache_clear()


def test_schedule_reboot_runs_sudo_reboot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REBOOT_ENABLED", "true")
    get_settings.cache_clear()
    monkeypatch.setattr("app.system.reboot.time.sleep", lambda _seconds: None)

    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(args)
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("app.system.reboot.subprocess.run", fake_run)

    assert schedule_reboot(delay_seconds=0) is True

    import time

    deadline = time.time() + 2.0
    while not calls and time.time() < deadline:
        time.sleep(0.01)

    assert calls == [["sudo", "/usr/sbin/reboot"]]
    get_settings.cache_clear()


def test_schedule_reboot_falls_back_to_systemctl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REBOOT_ENABLED", "true")
    get_settings.cache_clear()
    monkeypatch.setattr("app.system.reboot.time.sleep", lambda _seconds: None)

    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(args)
        if args == ["sudo", "/usr/sbin/reboot"]:
            return MagicMock(returncode=1, stdout="", stderr="permission denied")
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("app.system.reboot.subprocess.run", fake_run)

    assert schedule_reboot(delay_seconds=0) is True

    import time

    deadline = time.time() + 2.0
    while len(calls) < 2 and time.time() < deadline:
        time.sleep(0.01)

    assert calls == [
        ["sudo", "/usr/sbin/reboot"],
        ["sudo", "/bin/systemctl", "reboot"],
    ]
    get_settings.cache_clear()
