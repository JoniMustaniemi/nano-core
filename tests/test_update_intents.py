from app.assistant.rules import needs_update_confirmation


def test_update_request_matches_common_phrases() -> None:
    assert needs_update_confirmation("Update nano.")
    assert needs_update_confirmation("Check for updates.")
    assert needs_update_confirmation("Install update.")


def test_update_request_does_not_match_unrelated_phrases() -> None:
    assert not needs_update_confirmation("What's the weather?")
    assert not needs_update_confirmation("Restart yourself.")
