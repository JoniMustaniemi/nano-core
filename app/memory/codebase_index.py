from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session, col, select

import app.memory.db as db
from app.memory.models import CodebaseFileRecord
from app.proactive.codebase_files import file_content_hash, package_for_path


def sync_paths(paths: list[str]) -> None:
    """Ensure every known path exists in the ledger."""
    with Session(db.engine) as session:
        existing = {
            record.path: record for record in session.exec(select(CodebaseFileRecord)).all()
        }
        for path in paths:
            if path in existing:
                continue
            session.add(
                CodebaseFileRecord(
                    path=path,
                    package=package_for_path(path),
                )
            )
        session.commit()


def get_record(path: str) -> CodebaseFileRecord | None:
    with Session(db.engine) as session:
        statement = select(CodebaseFileRecord).where(CodebaseFileRecord.path == path)
        return session.exec(statement).first()


def list_records_for_selection(*, limit: int = 40) -> list[CodebaseFileRecord]:
    statement = (
        select(CodebaseFileRecord)
        .where(col(CodebaseFileRecord.last_scanned_at).is_not(None))
        .order_by(col(CodebaseFileRecord.last_scanned_at).desc())
        .limit(limit)
    )
    with Session(db.engine) as session:
        return list(session.exec(statement))


def _needs_scan(record: CodebaseFileRecord | None, current_hash: str) -> bool:
    if record is None:
        return True
    if record.last_scanned_at is None:
        return True
    return record.content_hash != current_hash


def _scan_sort_key(path: str, scanned_at: datetime | None) -> tuple[int, datetime, str]:
    if scanned_at is None:
        return (0, datetime.min.replace(tzinfo=UTC), path)
    return (1, scanned_at, path)


def pick_next_scan_target(*, all_paths: list[str]) -> str | None:
    """Pick the next file to scan using package-fair oldest-first rotation."""
    sync_paths(all_paths)
    pending_by_package: dict[str, list[tuple[str, datetime | None]]] = {}

    for path in all_paths:
        current_hash = file_content_hash(path)
        record = get_record(path)
        if not _needs_scan(record, current_hash):
            continue
        package = package_for_path(path)
        scanned_at = record.last_scanned_at if record is not None else None
        pending_by_package.setdefault(package, []).append((path, scanned_at))

    if not pending_by_package:
        return None

    def package_priority(package: str) -> tuple[int, datetime, str]:
        candidates = pending_by_package[package]
        path, scanned_at = min(candidates, key=lambda item: _scan_sort_key(item[0], item[1]))
        sort_key = _scan_sort_key(path, scanned_at)
        return (sort_key[0], sort_key[1], package)

    chosen_package = min(pending_by_package.keys(), key=package_priority)
    candidates = pending_by_package[chosen_package]
    path, _ = min(candidates, key=lambda item: _scan_sort_key(item[0], item[1]))
    return path


def upsert_scan_result(
    *,
    path: str,
    content_hash: str,
    summary: str,
    last_suggestion: str | None,
    last_confidence: str | None,
    scanned_at: datetime | None = None,
) -> CodebaseFileRecord:
    current = scanned_at or datetime.now(UTC)
    with Session(db.engine) as session:
        statement = select(CodebaseFileRecord).where(CodebaseFileRecord.path == path)
        record = session.exec(statement).first()
        if record is None:
            record = CodebaseFileRecord(
                path=path,
                package=package_for_path(path),
            )
        record.content_hash = content_hash
        record.summary = summary
        record.last_suggestion = last_suggestion
        record.last_confidence = last_confidence
        record.last_scanned_at = current
        session.add(record)
        session.commit()
        session.refresh(record)
        return record
