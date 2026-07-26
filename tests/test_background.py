from app.runtime.background import run_background


def test_run_background_uses_non_daemon_thread() -> None:
    thread = run_background(lambda: None, label="test-background")

    assert thread.daemon is False
