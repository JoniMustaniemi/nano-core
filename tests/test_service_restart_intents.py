from app.assistant.rules.intents import (
    needs_reboot_confirmation,
    needs_service_restart_confirmation,
)


def test_service_restart_matches_nano_restart_phrases() -> None:
    assert needs_service_restart_confirmation("Restart yourself.")
    assert needs_service_restart_confirmation("Restart nano.")
    assert needs_service_restart_confirmation("Restart the service.")


def test_service_restart_excludes_pi_restart_phrases() -> None:
    assert not needs_service_restart_confirmation("Restart the Raspberry Pi.")
    assert not needs_service_restart_confirmation("Restart the system.")


def test_pi_restart_routes_to_reboot_not_service_restart() -> None:
    assert needs_reboot_confirmation("Restart the Raspberry Pi.")
    assert not needs_service_restart_confirmation("Restart the Raspberry Pi.")
