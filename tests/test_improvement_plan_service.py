from __future__ import annotations

import json
from types import SimpleNamespace

from app.memory import improvement_plans
from app.memory.db import create_db_and_tables
from app.tools.improvement_plan_service import ImprovementPlanService, _plan_title
from app.tools.self_improve_planning import fallback_files_for_goal


def _settings(**overrides):
    values = {
        "self_improve_allowed_prefix": "app/",
        "self_improve_max_files": 5,
        "self_improve_max_file_chars": 8000,
        "llm_max_tokens": 512,
        "self_improve_plan_max_tokens": 8192,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_plan_title_strips_draft_plan_meta_phrasing() -> None:
    title = _plan_title(
        goal="Draft an improvement plan for clearer timer messages.",
        files=["app/assistant/rules/messages.py"],
    )
    assert title == "clearer timer messages"


def test_has_unprocessed_plan_blocks_second_draft(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'gate.sqlite3'}")
    create_db_and_tables()
    improvement_plans.create_plan(
        title="Pending plan",
        goal="clearer timer errors",
        body="Summary\n- do something",
        files=["app/main.py"],
    )

    class _Client:
        def complete(self, messages, **kwargs) -> str:
            return "Summary\n- do something else"

    monkeypatch.setattr("app.config.get_settings", lambda: _settings())
    result = ImprovementPlanService().draft(client=_Client(), goal="clearer timer errors")

    assert result.ok is False
    assert result.step == "gate"


def test_draft_service_saves_plan(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'draft.sqlite3'}")
    create_db_and_tables()
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("value = 1\n", encoding="utf-8")

    class _Client:
        def complete(self, messages, **kwargs) -> str:
            user_content = messages[-1]["content"]
            if "Known files:" in user_content:
                return '{"files_to_read": ["app/main.py"]}'
            return (
                "Summary\n"
                "Improve startup logging.\n\n"
                "Files to change\n"
                "- app/main.py\n\n"
                "Proposed changes\n"
                "- Add clearer boot messages.\n"
            )

    monkeypatch.setattr(
        "app.tools.self_improve_planning.file_selection_lines",
        lambda goal, limit=40: ["- app/main.py: Main entrypoint."],
    )
    monkeypatch.setattr("app.config.get_settings", lambda: _settings())

    result = ImprovementPlanService().draft(client=_Client(), goal="clearer startup logs")

    assert result.ok is True
    assert result.plan_id is not None
    saved = improvement_plans.get_plan(result.plan_id)
    assert saved is not None
    assert saved.status == "pending"
    assert "Improve startup logging." in saved.body
    assert json.loads(saved.files_json) == ["app/main.py"]


def test_draft_service_uses_preferred_files_without_selection_llm(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'preferred.sqlite3'}")
    create_db_and_tables()
    path = "app/assistant/rules/messages.py"
    (tmp_path / "app" / "assistant" / "rules").mkdir(parents=True)
    (tmp_path / "app" / "assistant" / "rules" / "messages.py").write_text(
        "# header\nvalue = 1\n",
        encoding="utf-8",
    )
    selection_calls: list[str] = []

    class _Client:
        def complete(self, messages, **kwargs) -> str:
            user_content = messages[-1]["content"]
            if "Known files:" in user_content:
                selection_calls.append(user_content)
            return "Summary\n- improve helpers"

    monkeypatch.setattr("app.config.get_settings", lambda: _settings())

    result = ImprovementPlanService().draft(
        client=_Client(),
        goal="improve message helpers",
        preferred_files=[path],
    )

    assert result.ok is True
    assert selection_calls == []
    saved = improvement_plans.get_plan(result.plan_id or 0)
    assert saved is not None
    assert json.loads(saved.files_json) == [path]


def test_fallback_files_for_goal_matches_keywords() -> None:
    files = fallback_files_for_goal("improve message helpers", allowed="app/")
    assert "app/assistant/rules/messages.py" in files


def test_draft_service_announces_brief_completion_without_progress_reporter(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'complete.sqlite3'}")
    create_db_and_tables()
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("value = 1\n", encoding="utf-8")

    standby_calls: list[dict[str, str]] = []

    class _Client:
        def complete(self, messages, **kwargs) -> str:
            user_content = messages[-1]["content"]
            if "Known files:" in user_content:
                return '{"files_to_read": ["app/main.py"]}'
            return "Summary\nOne focused change."

    monkeypatch.setattr(
        "app.tools.self_improve_planning.file_selection_lines",
        lambda goal, limit=40: ["- app/main.py: Main entrypoint."],
    )
    monkeypatch.setattr("app.config.get_settings", lambda: _settings())
    monkeypatch.setattr(
        "app.tools.improvement_plan_service.activity.standby",
        lambda **kwargs: standby_calls.append(kwargs) or None,
    )

    result = ImprovementPlanService().draft(client=_Client(), goal="clearer startup logs")

    assert result.ok is True
    assert len(standby_calls) == 1
    assert standby_calls[0]["source"] == "tools.improvement_plan_service.completed"
    assert "Theme:" in standby_calls[0]["detail"]
    assert "Plans tab" in standby_calls[0]["detail"]
