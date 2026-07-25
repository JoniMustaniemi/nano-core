from __future__ import annotations

import json
import subprocess

import pytest

from app.memory import improvement_plans
from app.memory.db import create_db_and_tables
from app.tools.improvement_plan_implementation import (
    ImprovementPlanImplementationService,
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
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation._emit_voice_announcement",
        lambda message: announcements.append(message),
    )

    class _PrService:
        def run(self, *, client, announce=True) -> PrResult:
            return PrResult(
                ok=True,
                step="complete",
                url="https://github.com/example/repo/pull/1",
            )

    ImprovementPlanImplementationService(pr_service=_PrService()).run(plan_id)

    assert announcements[0] == "I'm implementing an improvement plan."
    assert announcements[1] == "I'm opening a pull request."
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
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation._emit_voice_announcement",
        lambda message: announcements.append(message),
    )

    class _PrService:
        def run(self, *, client, announce=True) -> PrResult:
            return PrResult(ok=False, step="lint", error="Lint checks failed.")

    ImprovementPlanImplementationService(pr_service=_PrService()).run(plan_id)

    assert any(
        "declined to commit anything or open a pull request" in msg.lower() for msg in announcements
    )


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
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation._emit_voice_announcement",
        lambda message: None,
    )
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


def test_implementation_service_restores_files_on_pr_failure(
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
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation._emit_voice_announcement",
        lambda message: None,
    )

    class _PrService:
        def run(self, *, client, announce=True) -> PrResult:
            return PrResult(ok=False, step="lint", error="Lint checks failed.")

    result = ImprovementPlanImplementationService(pr_service=_PrService()).run(plan_id)

    assert result.ok is False
    assert target.read_text(encoding="utf-8") == "OLD = 1\n"
    plan = improvement_plans.get_plan(plan_id)
    assert plan is not None
    assert plan.status == "pending"
