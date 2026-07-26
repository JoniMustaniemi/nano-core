from __future__ import annotations

import threading
import time

from app.memory import improvement_plans
from app.memory.db import create_db_and_tables
from app.tools import plan_implementation_runtime
from app.tools.improvement_plan_facade import ImprovementPlanFacade


def test_restore_pending_invalidates_execution_lease(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'lease.sqlite3'}")
    create_db_and_tables()
    plan = improvement_plans.create_plan(
        title="Clearer timer errors",
        goal="clearer timer errors",
        body="Summary\nImprove timer copy.",
        files=["app/runtime/status_copy.py"],
    )
    assert plan.id is not None
    assert improvement_plans.try_mark_implementing(plan.id) is True
    saved = improvement_plans.get_plan(plan.id)
    assert saved is not None
    lease = saved.implementing_lease
    assert lease is not None

    assert improvement_plans.restore_pending(plan.id) is True
    assert improvement_plans.lease_matches(plan.id, lease) is False


def test_reset_plan_rejects_while_worker_is_active(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'worker.sqlite3'}")
    create_db_and_tables()
    plan = improvement_plans.create_plan(
        title="Clearer timer errors",
        goal="clearer timer errors",
        body="Summary\nImprove timer copy.",
        files=["app/runtime/status_copy.py"],
    )
    assert plan.id is not None
    assert improvement_plans.try_mark_implementing(plan.id) is True
    started = threading.Event()
    release = threading.Event()

    def _worker() -> None:
        plan_implementation_runtime.register_worker(plan.id, threading.current_thread())
        started.set()
        release.wait()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    assert started.wait(timeout=1)
    assert plan_implementation_runtime.is_worker_live(plan.id)

    monkeypatch.setattr(
        "app.tools.improvement_plan_facade.cancel_and_wait",
        lambda plan_id, timeout=30.0: False,
    )

    try:
        assert ImprovementPlanFacade().reset_plan(plan.id) == "worker_active"
        saved = improvement_plans.get_plan(plan.id)
        assert saved is not None
        assert saved.status == "implementing"
    finally:
        release.set()
        thread.join(timeout=1)
        plan_implementation_runtime.unregister_worker(plan.id)


def test_reset_plan_succeeds_after_successful_cancel(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'cancel-ok.sqlite3'}")
    create_db_and_tables()
    plan = improvement_plans.create_plan(
        title="Clearer timer errors",
        goal="clearer timer errors",
        body="Summary\nImprove timer copy.",
        files=["app/runtime/status_copy.py"],
    )
    assert plan.id is not None
    assert improvement_plans.try_mark_implementing(plan.id) is True

    monkeypatch.setattr(
        "app.tools.improvement_plan_facade.is_worker_live",
        lambda plan_id: True,
    )
    monkeypatch.setattr(
        "app.tools.improvement_plan_facade.cancel_and_wait",
        lambda plan_id, timeout=30.0: True,
    )

    assert ImprovementPlanFacade().reset_plan(plan.id) == "ok"
    saved = improvement_plans.get_plan(plan.id)
    assert saved is not None
    assert saved.status == "pending"
    assert saved.implementing_lease is None


def test_reset_plan_succeeds_when_worker_already_restored_plan(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'already-pending.sqlite3'}")
    create_db_and_tables()
    plan = improvement_plans.create_plan(
        title="Clearer timer errors",
        goal="clearer timer errors",
        body="Summary\nImprove timer copy.",
        files=["app/runtime/status_copy.py"],
    )
    assert plan.id is not None
    assert improvement_plans.try_mark_implementing(plan.id) is True

    monkeypatch.setattr(
        "app.tools.improvement_plan_facade.is_worker_live",
        lambda plan_id: True,
    )

    def _cancel_and_restore(plan_id: int, timeout: float = 30.0) -> bool:
        improvement_plans.restore_pending(plan.id)
        return True

    monkeypatch.setattr(
        "app.tools.improvement_plan_facade.cancel_and_wait",
        _cancel_and_restore,
    )

    assert ImprovementPlanFacade().reset_plan(plan.id) == "ok"
    saved = improvement_plans.get_plan(plan.id)
    assert saved is not None
    assert saved.status == "pending"


def test_restore_stale_skips_live_worker(tmp_path, monkeypatch) -> None:
    from datetime import UTC, datetime, timedelta

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'stale-worker.sqlite3'}")
    create_db_and_tables()
    plan = improvement_plans.create_plan(
        title="Clearer timer errors",
        goal="clearer timer errors",
        body="Summary\nImprove timer copy.",
        files=["app/runtime/status_copy.py"],
    )
    assert plan.id is not None
    assert improvement_plans.try_mark_implementing(plan.id) is True
    saved = improvement_plans.get_plan(plan.id)
    assert saved is not None
    saved.implementing_started_at = datetime.now(UTC) - timedelta(minutes=20)
    from sqlmodel import Session

    import app.memory.db as db

    with Session(db.engine) as session:
        session.add(saved)
        session.commit()

    started = threading.Event()
    release = threading.Event()

    def _worker() -> None:
        plan_implementation_runtime.register_worker(plan.id, threading.current_thread())
        started.set()
        release.wait()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    assert started.wait(timeout=1)
    assert plan_implementation_runtime.is_worker_live(plan.id)

    try:
        assert improvement_plans.restore_stale_implementing_plans(max_age_seconds=900) == 0
        refreshed = improvement_plans.get_plan(plan.id)
        assert refreshed is not None
        assert refreshed.status == "implementing"
    finally:
        release.set()
        thread.join(timeout=1)
        plan_implementation_runtime.unregister_worker(plan.id)
        time.sleep(0)
