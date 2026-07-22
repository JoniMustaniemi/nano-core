from app.proactive.codebase_examine import CodebaseExamineService


class _SelectClient:
    def complete(self, messages) -> str:
        if "File index" in messages[-1]["content"]:
            return '{"files_to_read": ["app/main.py"]}'
        return (
            '{"suggestion": "Add clearer health messages.", '
            '"goal": "health copy", "confidence": "medium"}'
        )


def test_codebase_examine_returns_offer(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.proactive.codebase_examine.walk_app_files",
        lambda max_files=40: ["app/main.py"],
    )
    monkeypatch.setattr(
        "app.proactive.codebase_examine.read_text_file",
        lambda path: "print('nano')",
    )
    offer = CodebaseExamineService().run(client=_SelectClient())
    assert offer is not None
    assert offer.kind == "self_improvement_suggestion"
