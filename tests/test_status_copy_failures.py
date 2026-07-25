from app.runtime.status_copy import (
    lint_failure_detail,
    lint_failure_user_message,
    lint_failure_voice_message,
    pr_failure_voice_message,
)


def test_lint_failure_voice_message_extracts_file_hint() -> None:
    error = (
        "Type checks failed: app\\assistant\\flows\\planner.py:94: error: "
        "Argument incompatible  [arg-type]"
    )
    spoken = lint_failure_voice_message(error)

    assert "planner.py" in spoken
    assert "Brains" in spoken


def test_lint_failure_user_message_includes_checker_summary() -> None:
    error = "Type checks failed: app/tools/demo.py:1: error: example"
    message = lint_failure_user_message(error)

    assert "demo.py" in message
    assert "type checks failed" in message.lower()
    assert error in message


def test_lint_failure_detail_combines_error_and_output() -> None:
    detail = lint_failure_detail("Type checks failed.", "app/demo.py:1: error")

    assert "Type checks failed." in detail
    assert "app/demo.py:1: error" in detail


def test_pr_failure_voice_message_uses_lint_copy_for_lint_step() -> None:
    spoken = pr_failure_voice_message("Type checks failed.", step="lint")

    assert "Lint checks failed" in spoken
