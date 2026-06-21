from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session, select

import app.memory.db as db
from app.config import get_settings
from app.memory.models import Note
from app.voice.service import GladosVoiceService


@dataclass(frozen=True, slots=True)
class HealthCheckResult:
    name: str
    ok: bool
    detail: str


HealthCheck = Callable[[], HealthCheckResult]


def run_health_checks() -> list[HealthCheckResult]:
    return [check() for check in _HEALTH_CHECKS]


def _database_health_check() -> HealthCheckResult:
    try:
        with Session(db.engine) as session:
            list(session.exec(select(Note).limit(1)))
    except Exception as exc:
        return HealthCheckResult(
            name="database",
            ok=False,
            detail=f"Database check failed: {exc}",
        )
    return HealthCheckResult(
        name="database",
        ok=True,
        detail="Database is reachable.",
    )


def _database_size_health_check() -> HealthCheckResult:
    settings = get_settings()
    sqlite_path = db.sqlite_path
    if sqlite_path is None:
        return HealthCheckResult(
            name="database_size",
            ok=True,
            detail="Database size check is only available for SQLite.",
        )

    resolved_path = Path(sqlite_path)
    if not resolved_path.exists():
        return HealthCheckResult(
            name="database_size",
            ok=True,
            detail="Database file does not exist yet.",
        )

    size_bytes = resolved_path.stat().st_size
    threshold = settings.database_size_warning_bytes
    if size_bytes >= threshold:
        return HealthCheckResult(
            name="database_size",
            ok=False,
            detail=(
                f"Database size is {_format_bytes(size_bytes)}, which exceeds the "
                "warning threshold "
                f"of {_format_bytes(threshold)}."
            ),
        )
    return HealthCheckResult(
        name="database_size",
        ok=True,
        detail=(
            f"Database size is {_format_bytes(size_bytes)}, below the warning threshold "
            f"of {_format_bytes(threshold)}."
        ),
    )


def _voice_health_check() -> HealthCheckResult:
    status = GladosVoiceService().status()
    available = bool(status.get("available"))
    detail = str(status.get("detail", "Voice status is unknown."))
    return HealthCheckResult(
        name="voice",
        ok=available,
        detail=detail,
    )


def _llm_health_check() -> HealthCheckResult:
    settings = get_settings()
    if settings.llm_provider == "local" and not settings.llm_model_path:
        return HealthCheckResult(
            name="llm",
            ok=False,
            detail="Local model path is not configured.",
        )
    if (
        settings.llm_provider in {"ollama", "llama_cpp", "llama_cpp_server"}
        and not settings.llm_base_url
    ):
        return HealthCheckResult(
            name="llm",
            ok=False,
            detail="LLM base URL is not configured.",
        )
    return HealthCheckResult(
        name="llm",
        ok=True,
        detail=f"LLM provider {settings.llm_provider} is configured.",
    )


_HEALTH_CHECKS: tuple[HealthCheck, ...] = (
    _database_health_check,
    _database_size_health_check,
    _voice_health_check,
    _llm_health_check,
)


def _format_bytes(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"
