from app.tools.plan_body_parser import parse_plan_body, target_file_mismatch_warning


def test_parse_plan_body_extracts_sections() -> None:
    body = (
        "Summary\n"
        "Make timer errors clearer.\n\n"
        "Target file\n"
        "app/runtime/status_copy.py\n\n"
        "Proposed change\n"
        "- Update TIMER_ERROR constant\n"
        "- Add helper for formatting\n\n"
        "Risks\n"
        "- Copy may need voice polish"
    )

    parsed = parse_plan_body(body)

    assert parsed.summary == "Make timer errors clearer."
    assert parsed.target_file == "app/runtime/status_copy.py"
    assert parsed.proposed_changes == [
        "Update TIMER_ERROR constant",
        "Add helper for formatting",
    ]
    assert parsed.risks == ["Copy may need voice polish"]


def test_parse_plan_body_tolerates_proposed_changes_header() -> None:
    body = "Summary\nImprove startup logging.\n\nProposed changes\n- Add boot log line"

    parsed = parse_plan_body(body)

    assert parsed.summary == "Improve startup logging."
    assert parsed.proposed_changes == ["Add boot log line"]


def test_target_file_mismatch_warning() -> None:
    parsed = parse_plan_body("Summary\nTest\n\nTarget file\napp/other.py")
    warning = target_file_mismatch_warning(
        parsed,
        allowed_files=["app/runtime/status_copy.py"],
    )
    assert warning is not None
    assert "app/other.py" in warning


def test_target_file_mismatch_warning_none_when_match() -> None:
    parsed = parse_plan_body("Summary\nTest\n\nTarget file\napp/runtime/status_copy.py")
    warning = target_file_mismatch_warning(
        parsed,
        allowed_files=["app/runtime/status_copy.py"],
    )
    assert warning is None
