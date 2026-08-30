from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, create_engine

from app.config import get_settings
from app.memory import models  # noqa: F401
from app.memory.migrations import run_migrations


def _sqlite_path(database_url: str) -> Path | None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None
    return Path(database_url.removeprefix(prefix))


def get_engine() -> Engine:
    settings = get_settings()
    sqlite_path_value = _sqlite_path(settings.database_url)
    if sqlite_path_value is not None and sqlite_path_value.parent != Path("."):
        sqlite_path_value.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(settings.database_url, echo=False)


def get_sqlite_path() -> Path | None:
    return _sqlite_path(get_settings().database_url)


def create_db_and_tables() -> None:
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    run_migrations(engine)


def __getattr__(name: str) -> object:
    if name == "engine":
        return get_engine()
    if name == "sqlite_path":
        return get_sqlite_path()
    if name == "settings":
        return get_settings()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
