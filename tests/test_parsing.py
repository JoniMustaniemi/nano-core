from app.assistant.rules.parsing import extract_json, looks_like_truncated_json


def test_extract_json_parses_object_with_brace_inside_string() -> None:
    raw = '{"path": "app/x.py", "content": "if x == \\"}\\": pass"}'
    payload = extract_json(raw)
    assert payload == {"path": "app/x.py", "content": 'if x == "}": pass'}


def test_extract_json_ignores_trailing_text_after_balanced_object() -> None:
    raw = '{"ok": true} trailing prose'
    payload = extract_json(raw)
    assert payload == {"ok": True}


def test_extract_json_strips_markdown_fence() -> None:
    raw = '```json\n{"files_to_read": ["app/main.py"]}\n```'
    payload = extract_json(raw)
    assert payload == {"files_to_read": ["app/main.py"]}


def test_extract_json_returns_none_for_invalid_json() -> None:
    assert extract_json("not json at all") is None


def test_extract_json_returns_none_for_non_string_input() -> None:
    assert extract_json(None) is None


def test_looks_like_truncated_json_detects_cut_off_object() -> None:
    raw = '```json\n{"files": [{"path": "app/x.py", "content": "import asyncio\\nfrom fastapi imp'
    assert looks_like_truncated_json(raw) is True


def test_looks_like_truncated_json_returns_false_for_valid_json() -> None:
    raw = '{"files": [{"path": "app/x.py", "content": "ok"}]}'
    assert looks_like_truncated_json(raw) is False


def test_looks_like_truncated_json_returns_false_for_non_json() -> None:
    assert looks_like_truncated_json("not json at all") is False
