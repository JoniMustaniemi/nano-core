from __future__ import annotations

import json

from sqlmodel import Session, col, select

import app.memory.db as db
from app.memory.models import ImprovementPlan


def has_unprocessed_plan() -> bool:
    with Session(db.engine) as session:
        statement = select(ImprovementPlan.id).where(ImprovementPlan.status == "pending").limit(1)
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
