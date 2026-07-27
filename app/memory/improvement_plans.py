from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, col, select

import app.memory.db as db
from app.memory.models import ImprovementPlan
from app.tools.plan_implementation_runtime import issue_implementing_lease

_UNPROCESSED_STATUSES = ("pending", "implementing")
_DEFAULT_STALE_IMPLEMENTING_SECONDS = 15 * 60


def has_unprocessed_plan() -> bool:
    with Session(db.engine) as session:
        statement = (
            select(ImprovementPlan.id)
            .where(col(ImprovementPlan.status).in_(_UNPROCESSED_STATUSES))
            .limit(1)
        )
        return session.exec(statement).first() is not None


def get_unprocessed_plan() -> ImprovementPlan | None:
    with Session(db.engine) as session:
        statement = (
            select(ImprovementPlan)
            .where(ImprovementPlan.status == "pending")
            .order_by(col(ImprovementPlan.created_at).desc())
            .limit(1)
        )
        return session.exec(statement).first()


def list_plans(*, limit: int = 20) -> list[ImprovementPlan]:
    statement = (
        select(ImprovementPlan).order_by(col(ImprovementPlan.created_at).desc()).limit(limit)
    )
    with Session(db.engine) as session:
        return list(session.exec(statement))


def get_plan(plan_id: int) -> ImprovementPlan | None:
    with Session(db.engine) as session:
        return session.get(ImprovementPlan, plan_id)


def create_plan(
    *,
    title: str,
    goal: str,
    body: str,
    files: list[str],
    source_note_id: int | None = None,
) -> ImprovementPlan:
    with Session(db.engine) as session:
        plan = ImprovementPlan(
            title=title,
            goal=goal,
            body=body,
            files_json=json.dumps(files, ensure_ascii=False),
            status="pending",
            source_note_id=source_note_id,
        )
        session.add(plan)
        session.commit()
        session.refresh(plan)
        return plan


def delete_plan(plan_id: int) -> bool:
    with Session(db.engine) as session:
        plan = session.get(ImprovementPlan, plan_id)
        if plan is None:
            return False
        session.delete(plan)
        session.commit()
        return True


def try_mark_implementing(plan_id: int) -> bool:
    with Session(db.engine) as session:
        plan = session.get(ImprovementPlan, plan_id)
        if plan is None or plan.status != "pending":
            return False
        plan.status = "implementing"
        plan.implementing_started_at = datetime.now(UTC)
        plan.implementing_lease = issue_implementing_lease()
        session.add(plan)
        session.commit()
        return True


def lease_matches(plan_id: int, lease: str) -> bool:
    plan = get_plan(plan_id)
    return plan is not None and plan.status == "implementing" and plan.implementing_lease == lease


def restore_pending(plan_id: int) -> bool:
    with Session(db.engine) as session:
        plan = session.get(ImprovementPlan, plan_id)
        if plan is None or plan.status != "implementing":
            return False
        plan.status = "pending"
        plan.implementing_started_at = None
        plan.implementing_lease = None
        session.add(plan)
        session.commit()
        return True


def restore_stale_implementing_plans(
    *,
    max_age_seconds: int = _DEFAULT_STALE_IMPLEMENTING_SECONDS,
) -> int:
    """Reset plans stuck in implementing longer than max_age_seconds."""
    from app.tools.plan_implementation_runtime import is_worker_live

    cutoff = datetime.now(UTC) - timedelta(seconds=max_age_seconds)
    candidate_ids: list[int] = []
    with Session(db.engine) as session:
        statement = select(ImprovementPlan).where(ImprovementPlan.status == "implementing")
        for plan in session.exec(statement):
            if plan.id is None:
                continue
            started_at = plan.implementing_started_at
            if started_at is not None and started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=UTC)
            if started_at is None or started_at <= cutoff:
                candidate_ids.append(plan.id)

    restored = 0
    for plan_id in candidate_ids:
        if is_worker_live(plan_id):
            continue
        if restore_pending(plan_id):
            restored += 1
    return restored


def files_from_plan(plan: ImprovementPlan) -> list[str]:
    try:
        files = json.loads(plan.files_json)
        if not isinstance(files, list):
            return []
    except json.JSONDecodeError:
        return []
    return [str(path) for path in files if str(path).strip()]
