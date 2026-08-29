from helpers.agent_fixtures import WipeConfirmationClient, agent_respond, patch_agent

from app.config import get_settings


def test_agent_requires_confirmation_before_service_restart(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SERVICE_RESTART_ENABLED", "true")
    get_settings.cache_clear()
    patch_agent(monkeypatch, client=WipeConfirmationClient(), tmp_path=tmp_path)

    content = agent_respond("Restart yourself.")

    assert "yes" in content.lower()
    assert "no" in content.lower()
    get_settings.cache_clear()


def test_agent_service_restart_disabled_without_config(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SERVICE_RESTART_ENABLED", "false")
    get_settings.cache_clear()
    patch_agent(monkeypatch, client=WipeConfirmationClient(), tmp_path=tmp_path)

    content = agent_respond("Restart yourself.")

    assert "disabled" in content.lower()
    get_settings.cache_clear()


def test_agent_restarts_after_confirmation(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SERVICE_RESTART_ENABLED", "true")
    get_settings.cache_clear()
    patch_agent(monkeypatch, client=WipeConfirmationClient(), tmp_path=tmp_path)
    scheduled: list[bool] = []
    monkeypatch.setattr(
        "app.assistant.flows.service_restart.schedule_service_restart",
        lambda: scheduled.append(True) or True,
    )

    first = agent_respond("Restart yourself.")
    second = agent_respond("yes")

    assert "yes" in first.lower()
    assert "no" in first.lower()
    assert second == "Restarting Nano now."
    assert scheduled == [True]
    get_settings.cache_clear()


def test_agent_cancels_service_restart_on_no(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SERVICE_RESTART_ENABLED", "true")
    get_settings.cache_clear()
    patch_agent(monkeypatch, client=WipeConfirmationClient(), tmp_path=tmp_path)

    agent_respond("Restart yourself.")
    content = agent_respond("no")

    assert content == "Service restart cancelled."
    get_settings.cache_clear()


def test_restart_pi_routes_to_reboot_not_service_restart(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("REBOOT_ENABLED", "true")
    monkeypatch.setenv("SERVICE_RESTART_ENABLED", "true")
    get_settings.cache_clear()
    patch_agent(monkeypatch, client=WipeConfirmationClient(), tmp_path=tmp_path)

    content = agent_respond("Restart the Raspberry Pi.")

    assert "yes" in content.lower()
    assert "no" in content.lower()
    get_settings.cache_clear()
