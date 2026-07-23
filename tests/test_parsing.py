from app.assistant.rules.parsing import extract_json


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
