from __future__ import annotations

import json
import subprocess

import pytest
from helpers.voice_announce import patch_announce_voice, silence_announce_voice

from app.memory import improvement_plans
from app.memory.db import create_db_and_tables
from app.tools.improvement_plan_implementation import (
    ImprovementPlanImplementationService,
    _apply_replacements,
    _build_apply_messages,
    _prefer_full_file_apply,
    _retry_assistant_content,
    check_implementation_preflight,
)
from app.tools.pr_service import PrResult


def _init_git_repo(path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "-A"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "baseline"],
        cwd=path,
        check=True,
        capture_output=True,
    )


def _create_plan(**overrides) -> int:
    create_db_and_tables()
    plan = improvement_plans.create_plan(
        title=overrides.get("title", "Clearer timer errors"),
        goal=overrides.get("goal", "clearer timer errors"),
        body=overrides.get("body", "Summary\nImprove timer copy."),
        files=overrides.get("files", ["app/runtime/status_copy.py"]),
    )
    assert plan.id is not None
    return plan.id


def _pass_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.is_git_repo",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.gh_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.gh_authenticated",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.working_tree_dirty",
        lambda: False,
    )
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_open_pull_request",
        lambda: None,
    )


def test_check_implementation_preflight_rejects_missing_plan() -> None:
    result = check_implementation_preflight(None)
    assert result.ok is False
    assert result.status_code == 404


def test_check_implementation_preflight_rejects_non_pending_status(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'status.sqlite3'}")
    plan_id = _create_plan()
    improvement_plans.try_mark_implementing(plan_id)

    plan = improvement_plans.get_plan(plan_id)
    result = check_implementation_preflight(plan)
    assert result.ok is False
    assert result.status_code == 409


def test_check_implementation_preflight_rejects_dirty_tree(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'dirty.sqlite3'}")
    plan_id = _create_plan()
    plan = improvement_plans.get_plan(plan_id)
    _pass_preflight(monkeypatch)
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.working_tree_dirty",
        lambda: True,
    )

    result = check_implementation_preflight(plan)
    assert result.ok is False
    assert "uncommitted changes" in (result.error or "").lower()


def test_try_mark_implementing_and_restore_pending(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'mutex.sqlite3'}")
    plan_id = _create_plan()

    assert improvement_plans.try_mark_implementing(plan_id) is True
    plan = improvement_plans.get_plan(plan_id)
    assert plan is not None
    assert plan.status == "implementing"
    assert improvement_plans.has_unprocessed_plan() is True

    assert improvement_plans.try_mark_implementing(plan_id) is False

    assert improvement_plans.restore_pending(plan_id) is True
    plan = improvement_plans.get_plan(plan_id)
    assert plan is not None
    assert plan.status == "pending"


def test_implementation_service_applies_plan_and_opens_pr(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'success.sqlite3'}")
    (tmp_path / "app" / "runtime").mkdir(parents=True)
    target = tmp_path / "app" / "runtime" / "status_copy.py"
    target.write_text("OLD = 1\n", encoding="utf-8")

    plan_id = _create_plan()
    assert improvement_plans.try_mark_implementing(plan_id) is True
    _pass_preflight(monkeypatch)

    class _Client:
        def complete(self, messages, **kwargs) -> str:
            return '{"files": [{"path": "app/runtime/status_copy.py", "content": "NEW = 2\\n"}]}'

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_code_llm_client",
        lambda: _Client(),
    )

    class _PrService:
        def run(self, *, client, announce=True) -> PrResult:
            return PrResult(
                ok=True,
                step="complete",
                url="https://github.com/example/repo/pull/1",
            )

    result = ImprovementPlanImplementationService(pr_service=_PrService()).run(plan_id)

    assert result.ok is True
    assert result.pr_url == "https://github.com/example/repo/pull/1"
    assert target.read_text(encoding="utf-8") == "NEW = 2\n"
    assert improvement_plans.get_plan(plan_id) is None


def test_implementation_service_restores_pending_on_pr_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'pr-fail.sqlite3'}")
    (tmp_path / "app" / "runtime").mkdir(parents=True)
    target = tmp_path / "app" / "runtime" / "status_copy.py"
    target.write_text("OLD = 1\n", encoding="utf-8")

    plan_id = _create_plan()
    assert improvement_plans.try_mark_implementing(plan_id) is True
    _pass_preflight(monkeypatch)

    class _Client:
        def complete(self, messages, **kwargs) -> str:
            return '{"files": [{"path": "app/runtime/status_copy.py", "content": "NEW = 2\\n"}]}'

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_code_llm_client",
        lambda: _Client(),
    )

    class _PrService:
        def run(self, *, client, announce=True) -> PrResult:
            return PrResult(ok=False, step="lint", error="Lint checks failed.")

    result = ImprovementPlanImplementationService(pr_service=_PrService()).run(plan_id)

    assert result.ok is False
    assert result.step == "lint"
    plan = improvement_plans.get_plan(plan_id)
    assert plan is not None
    assert plan.status == "pending"


def test_implementation_service_announces_key_steps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'announce.sqlite3'}")
    (tmp_path / "app" / "runtime").mkdir(parents=True)
    target = tmp_path / "app" / "runtime" / "status_copy.py"
    target.write_text("OLD = 1\n", encoding="utf-8")

    plan_id = _create_plan()
    assert improvement_plans.try_mark_implementing(plan_id) is True
    _pass_preflight(monkeypatch)

    announcements: list[str] = []

    class _Client:
        def complete(self, messages, **kwargs) -> str:
            return '{"files": [{"path": "app/runtime/status_copy.py", "content": "NEW = 2\\n"}]}'

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_code_llm_client",
        lambda: _Client(),
    )
    patch_announce_voice(monkeypatch, announcements)

    class _PrService:
        def run(self, *, client, announce=True) -> PrResult:
            return PrResult(
                ok=True,
                step="complete",
                url="https://github.com/example/repo/pull/1",
            )

    ImprovementPlanImplementationService(pr_service=_PrService()).run(plan_id)

    assert announcements[0] == "I'm implementing an improvement plan."
    assert announcements[-1] == "I implemented the improvement plan."


def test_implementation_service_announces_lint_failure_message(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'lint-announce.sqlite3'}")
    (tmp_path / "app" / "runtime").mkdir(parents=True)
    target = tmp_path / "app" / "runtime" / "status_copy.py"
    target.write_text("OLD = 1\n", encoding="utf-8")

    plan_id = _create_plan()
    assert improvement_plans.try_mark_implementing(plan_id) is True
    _pass_preflight(monkeypatch)

    announcements: list[str] = []

    class _Client:
        def complete(self, messages, **kwargs) -> str:
            return '{"files": [{"path": "app/runtime/status_copy.py", "content": "NEW = 2\\n"}]}'

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_code_llm_client",
        lambda: _Client(),
    )
    patch_announce_voice(monkeypatch, announcements)

    class _PrService:
        def run(self, *, client, announce=True) -> PrResult:
            return PrResult(ok=False, step="lint", error="Lint checks failed.")

    ImprovementPlanImplementationService(pr_service=_PrService()).run(plan_id)

    assert any(
        "changes were applied" in msg.lower() and "create pull request" in msg.lower()
        for msg in announcements
    )


def test_implementation_service_passes_plan_max_tokens_to_apply_llm(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tokens.sqlite3'}")
    (tmp_path / "app" / "runtime").mkdir(parents=True)
    (tmp_path / "app" / "runtime" / "status_copy.py").write_text("OLD = 1\n", encoding="utf-8")

    plan_id = _create_plan()
    assert improvement_plans.try_mark_implementing(plan_id) is True
    _pass_preflight(monkeypatch)

    captured: list[dict[str, int | float | None]] = []

    class _Client:
        def complete(self, messages, **kwargs) -> str:
            captured.append(
                {
                    "max_tokens": kwargs.get("max_tokens"),
                    "temperature": kwargs.get("temperature"),
                }
            )
            return '{"files": [{"path": "app/runtime/status_copy.py", "content": "NEW = 2\\n"}]}'

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_code_llm_client",
        lambda: _Client(),
    )
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_llm_client",
        lambda: _Client(),
    )
    silence_announce_voice(monkeypatch)

    class _PrService:
        def run(self, *, client, announce=True) -> PrResult:
            return PrResult(ok=True, step="complete", url="https://github.com/example/repo/pull/9")

    ImprovementPlanImplementationService(pr_service=_PrService()).run(plan_id)

    assert captured
    assert captured[0]["max_tokens"] == 8192
    assert captured[0]["temperature"] == 0.2


def test_implementation_service_restores_pending_on_apply_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'apply-fail.sqlite3'}")
    (tmp_path / "app" / "runtime").mkdir(parents=True)
    (tmp_path / "app" / "runtime" / "status_copy.py").write_text("OLD = 1\n", encoding="utf-8")

    plan_id = _create_plan()
    assert improvement_plans.try_mark_implementing(plan_id) is True
    _pass_preflight(monkeypatch)

    class _Client:
        def complete(self, messages, **kwargs) -> str:
            return "not json"

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_code_llm_client",
        lambda: _Client(),
    )

    result = ImprovementPlanImplementationService().run(plan_id)

    assert result.ok is False
    assert result.step == "apply"
    plan = improvement_plans.get_plan(plan_id)
    assert plan is not None
    assert plan.status == "pending"


def test_implementation_service_rejects_no_op_apply(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'noop.sqlite3'}")
    (tmp_path / "app" / "runtime").mkdir(parents=True)
    target = tmp_path / "app" / "runtime" / "status_copy.py"
    original = "OLD = 1\n"
    target.write_text(original, encoding="utf-8")

    plan_id = _create_plan()
    assert improvement_plans.try_mark_implementing(plan_id) is True
    _pass_preflight(monkeypatch)

    class _Client:
        def complete(self, messages, **kwargs) -> str:
            return json.dumps(
                {
                    "files": [
                        {
                            "path": "app/runtime/status_copy.py",
                            "content": original,
                        }
                    ]
                }
            )

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_code_llm_client",
        lambda: _Client(),
    )

    result = ImprovementPlanImplementationService().run(plan_id)

    assert result.ok is False
    assert result.step == "apply"
    assert "no file diff" in (result.error or "").lower()
    assert target.read_text(encoding="utf-8") == original


def test_implementation_service_normalizes_apply_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'normalize.sqlite3'}")
    (tmp_path / "app" / "runtime").mkdir(parents=True)
    target = tmp_path / "app" / "runtime" / "status_copy.py"
    target.write_text("OLD = 1\n", encoding="utf-8")

    plan_id = _create_plan()
    assert improvement_plans.try_mark_implementing(plan_id) is True
    _pass_preflight(monkeypatch)

    class _Client:
        def complete(self, messages, **kwargs) -> str:
            return '{"files": [{"path": "./app/runtime/status_copy.py", "content": "NEW = 2\\n"}]}'

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_code_llm_client",
        lambda: _Client(),
    )

    class _PrService:
        def run(self, *, client, announce=True) -> PrResult:
            return PrResult(ok=True, step="complete", url="https://github.com/example/repo/pull/2")

    result = ImprovementPlanImplementationService(pr_service=_PrService()).run(plan_id)

    assert result.ok is True
    assert target.read_text(encoding="utf-8") == "NEW = 2\n"


def test_implementation_success_activity_detail_has_no_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'detail.sqlite3'}")
    (tmp_path / "app" / "runtime").mkdir(parents=True)
    target = tmp_path / "app" / "runtime" / "status_copy.py"
    target.write_text("OLD = 1\n", encoding="utf-8")

    plan_id = _create_plan()
    assert improvement_plans.try_mark_implementing(plan_id) is True
    _pass_preflight(monkeypatch)

    standby_calls: list[dict[str, str | None]] = []

    class _Client:
        def complete(self, messages, **kwargs) -> str:
            return '{"files": [{"path": "app/runtime/status_copy.py", "content": "NEW = 2\\n"}]}'

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_code_llm_client",
        lambda: _Client(),
    )
    silence_announce_voice(monkeypatch)
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.activity.standby",
        lambda **kwargs: standby_calls.append(kwargs) or None,
    )

    class _PrService:
        def run(self, *, client, announce=True) -> PrResult:
            return PrResult(
                ok=True,
                step="complete",
                url="https://github.com/example/repo/pull/3",
            )

    result = ImprovementPlanImplementationService(pr_service=_PrService()).run(plan_id)

    assert result.ok is True
    assert improvement_plans.get_plan(plan_id) is None
    assert standby_calls
    detail = standby_calls[-1].get("detail") or ""
    assert "github.com" not in detail
    assert "http" not in detail.lower()


def test_implementation_service_keeps_files_on_pr_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'restore.sqlite3'}")
    (tmp_path / "app" / "runtime").mkdir(parents=True)
    target = tmp_path / "app" / "runtime" / "status_copy.py"
    target.write_text("OLD = 1\n", encoding="utf-8")
    _init_git_repo(tmp_path)

    plan_id = _create_plan()
    assert improvement_plans.try_mark_implementing(plan_id) is True
    _pass_preflight(monkeypatch)

    class _Client:
        def complete(self, messages, **kwargs) -> str:
            return '{"files": [{"path": "app/runtime/status_copy.py", "content": "NEW = 2\\n"}]}'

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_code_llm_client",
        lambda: _Client(),
    )
    silence_announce_voice(monkeypatch)

    class _PrService:
        def run(self, *, client, announce=True) -> PrResult:
            return PrResult(ok=False, step="lint", error="Lint checks failed.")

    result = ImprovementPlanImplementationService(pr_service=_PrService()).run(plan_id)

    assert result.ok is False
    assert target.read_text(encoding="utf-8") == "NEW = 2\n"
    plan = improvement_plans.get_plan(plan_id)
    assert plan is not None
    assert plan.status == "pending"


def test_apply_replacements_requires_unique_find_text() -> None:
    content = "OLD = 1\nOTHER = 1\n"
    result = _apply_replacements(content, [("OLD = 1\n", "NEW = 2\n")])
    assert result == "NEW = 2\nOTHER = 1\n"

    with pytest.raises(ValueError, match="exactly once"):
        _apply_replacements(content, [("= 1", "x")])

    with pytest.raises(ValueError, match="exactly once"):
        _apply_replacements("OLD = 1\n", [("missing", "x")])


def test_implementation_service_applies_replacement_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'replace.sqlite3'}")
    (tmp_path / "app" / "runtime").mkdir(parents=True)
    target = tmp_path / "app" / "runtime" / "status_copy.py"
    target.write_text("OLD = 1\n", encoding="utf-8")

    plan_id = _create_plan()
    assert improvement_plans.try_mark_implementing(plan_id) is True
    _pass_preflight(monkeypatch)

    class _Client:
        def complete(self, messages, **kwargs) -> str:
            return json.dumps(
                {
                    "files": [
                        {
                            "path": "app/runtime/status_copy.py",
                            "replacements": [{"find": "OLD = 1", "replace": "NEW = 2"}],
                        }
                    ]
                }
            )

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_code_llm_client",
        lambda: _Client(),
    )

    class _PrService:
        def run(self, *, client, announce=True) -> PrResult:
            return PrResult(ok=True, step="complete", url="https://github.com/example/repo/pull/4")

    result = ImprovementPlanImplementationService(pr_service=_PrService()).run(plan_id)

    assert result.ok is True
    assert target.read_text(encoding="utf-8") == "NEW = 2\n"


def test_implementation_service_rejects_ambiguous_replacement_find(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'ambiguous.sqlite3'}")
    (tmp_path / "app" / "runtime").mkdir(parents=True)
    target = tmp_path / "app" / "runtime" / "status_copy.py"
    target.write_text("OLD = 1\nDUP = 1\n", encoding="utf-8")

    plan_id = _create_plan()
    assert improvement_plans.try_mark_implementing(plan_id) is True
    _pass_preflight(monkeypatch)

    class _Client:
        def complete(self, messages, **kwargs) -> str:
            return json.dumps(
                {
                    "files": [
                        {
                            "path": "app/runtime/status_copy.py",
                            "replacements": [{"find": "= 1", "replace": "= 2"}],
                        }
                    ]
                }
            )

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_code_llm_client",
        lambda: _Client(),
    )
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_llm_client",
        lambda: _Client(),
    )
    from types import SimpleNamespace

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_settings",
        lambda: SimpleNamespace(
            self_improve_allowed_prefix="app/",
            self_improve_plan_max_tokens=8192,
            self_improve_apply_max_attempts=1,
        ),
    )

    result = ImprovementPlanImplementationService().run(plan_id)

    assert result.ok is False
    assert result.step == "apply"
    assert "exactly once" in (result.error or "").lower()
    assert target.read_text(encoding="utf-8") == "OLD = 1\nDUP = 1\n"
    plan = improvement_plans.get_plan(plan_id)
    assert plan is not None
    assert plan.status == "pending"


def test_implementation_service_reports_invalid_json_with_preview(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'invalid-json.sqlite3'}")
    (tmp_path / "app" / "runtime").mkdir(parents=True)
    (tmp_path / "app" / "runtime" / "status_copy.py").write_text("OLD = 1\n", encoding="utf-8")

    plan_id = _create_plan()
    assert improvement_plans.try_mark_implementing(plan_id) is True
    _pass_preflight(monkeypatch)

    class _Client:
        def complete(self, messages, **kwargs) -> str:
            return "not json at all"

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_code_llm_client",
        lambda: _Client(),
    )
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_llm_client",
        lambda: _Client(),
    )
    from types import SimpleNamespace

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_settings",
        lambda: SimpleNamespace(
            self_improve_allowed_prefix="app/",
            self_improve_plan_max_tokens=8192,
            self_improve_apply_max_attempts=2,
        ),
    )

    result = ImprovementPlanImplementationService().run(plan_id)

    assert result.ok is False
    assert result.step == "apply"
    assert "invalid json after 4 attempts" in (result.error or "").lower()
    assert "not json at all" in (result.error or "")


def test_implementation_service_uses_configured_apply_max_attempts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'attempts.sqlite3'}")
    (tmp_path / "app" / "runtime").mkdir(parents=True)
    (tmp_path / "app" / "runtime" / "status_copy.py").write_text("OLD = 1\n", encoding="utf-8")

    plan_id = _create_plan()
    assert improvement_plans.try_mark_implementing(plan_id) is True
    _pass_preflight(monkeypatch)

    call_count = 0

    class _Client:
        def complete(self, messages, **kwargs) -> str:
            nonlocal call_count
            call_count += 1
            return "not json"

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_code_llm_client",
        lambda: _Client(),
    )
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_llm_client",
        lambda: _Client(),
    )
    from types import SimpleNamespace

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_settings",
        lambda: SimpleNamespace(
            self_improve_allowed_prefix="app/",
            self_improve_plan_max_tokens=8192,
            self_improve_apply_max_attempts=3,
        ),
    )

    result = ImprovementPlanImplementationService().run(plan_id)

    assert result.ok is False
    assert call_count == 6
    assert "invalid json after 6 attempts" in (result.error or "").lower()


def test_apply_plan_honours_cancellation_event(tmp_path, monkeypatch) -> None:
    from threading import Event

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'cancel-apply.sqlite3'}")
    (tmp_path / "app" / "runtime").mkdir(parents=True)
    (tmp_path / "app" / "runtime" / "status_copy.py").write_text("OLD = 1\n", encoding="utf-8")

    plan_id = _create_plan()
    plan = improvement_plans.get_plan(plan_id)
    assert plan is not None

    cancel_event = Event()
    cancel_event.set()

    result = ImprovementPlanImplementationService()._apply_plan(
        plan,
        allowed_files=["app/runtime/status_copy.py"],
        cancel_event=cancel_event,
    )

    assert result.ok is False
    assert result.step == "cancelled"


def test_prefer_full_file_apply_for_single_small_file() -> None:
    contents = {"app/runtime/status_copy.py": "OLD = 1\n"}
    assert _prefer_full_file_apply(contents) is True


def test_prefer_full_file_apply_false_for_multiple_files() -> None:
    contents = {
        "app/runtime/status_copy.py": "OLD = 1\n",
        "app/runtime/activity.py": "ACTIVITY = 1\n",
    }
    assert _prefer_full_file_apply(contents) is False


def test_prefer_full_file_apply_for_multi_step_plan() -> None:
    contents = {"app/runtime/status_copy.py": "OLD = 1\n"}
    proposed_changes = ["step one", "step two", "step three"]
    assert _prefer_full_file_apply(contents, proposed_changes=proposed_changes) is True


def test_build_apply_messages_includes_parsed_proposed_changes() -> None:
    body = (
        "Summary\n"
        "Make timer errors clearer.\n\n"
        "Target file\n"
        "app/runtime/status_copy.py\n\n"
        "Proposed change\n"
        "- Update TIMER_ERROR constant\n"
        "- Add helper for formatting"
    )
    messages = _build_apply_messages(
        goal="clearer timer errors",
        body=body,
        file_contents={"app/runtime/status_copy.py": "OLD = 1\n"},
        allowed_files=["app/runtime/status_copy.py"],
        prefer_full_file=False,
    )
    user_prompt = messages[1]["content"]
    assert "You MUST implement exactly these steps:" in user_prompt
    assert "Update TIMER_ERROR constant" in user_prompt
    assert "Add helper for formatting" in user_prompt


def test_build_apply_messages_prefers_full_file_for_small_target() -> None:
    messages = _build_apply_messages(
        goal="clearer timer errors",
        body="Summary\nImprove timer copy.",
        file_contents={"app/runtime/status_copy.py": "OLD = 1\n"},
        allowed_files=["app/runtime/status_copy.py"],
        prefer_full_file=True,
    )
    system_prompt = messages[0]["content"]
    assert "full updated file contents" in system_prompt
    assert "Do not use replacements" in system_prompt


def test_retry_assistant_content_truncates_large_failed_response() -> None:
    large = '{"files": [{"path": "app/x.py", "content": "' + ("x" * 2000) + '"}'
    preview = _retry_assistant_content(large)
    assert len(preview) < len(large)
    assert "truncated for context" in preview


def test_implementation_service_switches_to_full_file_correction_after_json_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'full-file-fallback.sqlite3'}")
    (tmp_path / "app" / "runtime").mkdir(parents=True)
    (tmp_path / "app" / "runtime" / "status_copy.py").write_text("OLD = 1\n", encoding="utf-8")

    plan_id = _create_plan()
    assert improvement_plans.try_mark_implementing(plan_id) is True
    _pass_preflight(monkeypatch)

    captured_corrections: list[str] = []
    call_count = 0

    class _Client:
        def complete(self, messages, **kwargs) -> str:
            nonlocal call_count
            call_count += 1
            for message in reversed(messages):
                if (
                    message.get("role") == "user"
                    and "invalid" in str(message.get("content", "")).lower()
                ):
                    captured_corrections.append(str(message["content"]))
                    break
            if call_count == 3:
                return (
                    '{"files": [{"path": "app/runtime/status_copy.py", "content": "NEW = 2\\n"}]}'
                )
            return '{"files": [{"path": "app/runtime/status_copy.py", "replacements":'

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_code_llm_client",
        lambda: _Client(),
    )
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_llm_client",
        lambda: _Client(),
    )
    from types import SimpleNamespace

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_settings",
        lambda: SimpleNamespace(
            self_improve_allowed_prefix="app/",
            self_improve_plan_max_tokens=8192,
            self_improve_apply_max_attempts=4,
        ),
    )
    silence_announce_voice(monkeypatch)

    class _PrService:
        def run(self, *, client, announce=True) -> PrResult:
            return PrResult(ok=True, step="complete", url="https://github.com/example/repo/pull/5")

    result = ImprovementPlanImplementationService(pr_service=_PrService()).run(plan_id)

    assert result.ok is True
    assert any("Required shape" in correction for correction in captured_corrections)
    assert any("cut off" in correction.lower() for correction in captured_corrections)


def test_implementation_service_refreshes_system_prompt_on_full_file_transition(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'system-refresh.sqlite3'}")
    (tmp_path / "app" / "runtime").mkdir(parents=True)
    target = tmp_path / "app" / "runtime" / "status_copy.py"
    target.write_text(
        "".join(f"LINE_{index} = {index}\n" for index in range(201)), encoding="utf-8"
    )

    plan_id = _create_plan()
    assert improvement_plans.try_mark_implementing(plan_id) is True
    _pass_preflight(monkeypatch)

    captured_system_prompts: list[str] = []
    call_count = 0

    class _Client:
        def complete(self, messages, **kwargs) -> str:
            nonlocal call_count
            call_count += 1
            captured_system_prompts.append(str(messages[0]["content"]))
            if call_count == 3:
                return (
                    '{"files": [{"path": "app/runtime/status_copy.py", "content": "NEW = 2\\n"}]}'
                )
            return "not json"

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_code_llm_client",
        lambda: _Client(),
    )
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_llm_client",
        lambda: _Client(),
    )
    from types import SimpleNamespace

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_settings",
        lambda: SimpleNamespace(
            self_improve_allowed_prefix="app/",
            self_improve_plan_max_tokens=8192,
            self_improve_apply_max_attempts=4,
        ),
    )
    silence_announce_voice(monkeypatch)

    class _PrService:
        def run(self, *, client, announce=True) -> PrResult:
            return PrResult(ok=True, step="complete", url="https://github.com/example/repo/pull/7")

    result = ImprovementPlanImplementationService(pr_service=_PrService()).run(plan_id)

    assert result.ok is True
    assert "minimal search/replace" in captured_system_prompts[0]
    assert "full updated file contents" in captured_system_prompts[2]


def test_implementation_service_retry_conversation_uses_short_assistant_preview(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'retry-hygiene.sqlite3'}")
    (tmp_path / "app" / "runtime").mkdir(parents=True)
    (tmp_path / "app" / "runtime" / "status_copy.py").write_text("OLD = 1\n", encoding="utf-8")

    plan_id = _create_plan()
    assert improvement_plans.try_mark_implementing(plan_id) is True
    _pass_preflight(monkeypatch)

    captured_messages: list[list[dict[str, str]]] = []
    call_count = 0
    huge_truncated = (
        '{"files": [{"path": "app/runtime/status_copy.py", "replacements": '
        '[{"find": "OLD", "replace": "' + ("x" * 3000)
    )

    class _Client:
        def complete(self, messages, **kwargs) -> str:
            nonlocal call_count
            call_count += 1
            captured_messages.append(list(messages))
            if call_count == 2:
                return (
                    '{"files": [{"path": "app/runtime/status_copy.py", "content": "NEW = 2\\n"}]}'
                )
            return huge_truncated

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_code_llm_client",
        lambda: _Client(),
    )
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_llm_client",
        lambda: _Client(),
    )
    from types import SimpleNamespace

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_settings",
        lambda: SimpleNamespace(
            self_improve_allowed_prefix="app/",
            self_improve_plan_max_tokens=8192,
            self_improve_apply_max_attempts=4,
        ),
    )
    silence_announce_voice(monkeypatch)

    class _PrService:
        def run(self, *, client, announce=True) -> PrResult:
            return PrResult(ok=True, step="complete", url="https://github.com/example/repo/pull/6")

    result = ImprovementPlanImplementationService(pr_service=_PrService()).run(plan_id)

    assert result.ok is True
    retry_messages = captured_messages[1]
    assistant_messages = [
        message["content"] for message in retry_messages if message.get("role") == "assistant"
    ]
    assert assistant_messages
    assert len(assistant_messages[-1]) < len(huge_truncated)
    assert "truncated for context" in assistant_messages[-1]


def test_implementation_service_reports_truncated_json_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'truncated-json.sqlite3'}")
    (tmp_path / "app" / "runtime").mkdir(parents=True)
    (tmp_path / "app" / "runtime" / "status_copy.py").write_text("OLD = 1\n", encoding="utf-8")

    plan_id = _create_plan()
    assert improvement_plans.try_mark_implementing(plan_id) is True
    _pass_preflight(monkeypatch)

    truncated = (
        '```json\n{"files": [{"path": "app/runtime/status_copy.py", "replacements": '
        '[{"find": "import asyncio", "replace": "import asyncio\\nfrom fastapi imp'
    )

    class _Client:
        def complete(self, messages, **kwargs) -> str:
            return truncated

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_code_llm_client",
        lambda: _Client(),
    )
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_llm_client",
        lambda: _Client(),
    )
    from types import SimpleNamespace

    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_settings",
        lambda: SimpleNamespace(
            self_improve_allowed_prefix="app/",
            self_improve_plan_max_tokens=8192,
            self_improve_apply_max_attempts=2,
        ),
    )

    result = ImprovementPlanImplementationService().run(plan_id)

    assert result.ok is False
    assert result.step == "apply"
    assert "truncated json after 4 attempts" in (result.error or "").lower()
    assert "larger code model" in (result.error or "").lower()
