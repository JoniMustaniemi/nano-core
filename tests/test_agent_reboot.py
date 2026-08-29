from helpers.agent_fixtures import WipeConfirmationClient, agent_respond, patch_agent

from app.config import get_settings


def test_agent_requires_confirmation_before_reboot(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("REBOOT_ENABLED", "true")
    get_settings.cache_clear()
    patch_agent(monkeypatch, client=WipeConfirmationClient(), tmp_path=tmp_path)

    content = agent_respond("Reboot the Raspberry Pi.")

    assert "yes" in content.lower()
    assert "no" in content.lower()
    get_settings.cache_clear()


def test_agent_reboot_disabled_without_config(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("REBOOT_ENABLED", "false")
    get_settings.cache_clear()
    patch_agent(monkeypatch, client=WipeConfirmationClient(), tmp_path=tmp_path)

    content = agent_respond("Reboot the Raspberry Pi.")

    assert "disabled" in content.lower()
    get_settings.cache_clear()


def test_agent_reboots_after_confirmation(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("REBOOT_ENABLED", "true")
    get_settings.cache_clear()
    patch_agent(monkeypatch, client=WipeConfirmationClient(), tmp_path=tmp_path)
    scheduled: list[bool] = []
    monkeypatch.setattr(
        "app.assistant.flows.reboot.schedule_reboot",
        lambda: scheduled.append(True) or True,
    )

    first = agent_respond("Reboot the Raspberry Pi.")
    second = agent_respond("yes")

    assert "yes" in first.lower()
    assert "no" in first.lower()
    assert second == "Rebooting the Raspberry Pi now."
    assert scheduled == [True]
    get_settings.cache_clear()


def test_agent_cancels_reboot_on_no(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("REBOOT_ENABLED", "true")
    get_settings.cache_clear()
    patch_agent(monkeypatch, client=WipeConfirmationClient(), tmp_path=tmp_path)

    agent_respond("Reboot the Raspberry Pi.")
    content = agent_respond("no")

    assert content == "Reboot cancelled."
    get_settings.cache_clear()
