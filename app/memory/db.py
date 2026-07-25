from pathlib import Path

from sqlalchemy import text
from sqlmodel import SQLModel, create_engine

from app.config import get_settings
from app.memory import models  # noqa: F401


def _sqlite_path(database_url: str) -> Path | None:
    """
    Return the SQLite filesystem path for a SQLite database URL.

    Args:
        database_url: Database URL to inspect.

    Returns:
        Parsed value when available; otherwise None.
    """
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None
    return Path(database_url.removeprefix(prefix))


settings = get_settings()
sqlite_path = _sqlite_path(settings.database_url)
if sqlite_path is not None and sqlite_path.parent != Path("."):
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(settings.database_url, echo=False)


def create_db_and_tables() -> None:
    """
    Create configured database tables if they do not already exist.

    Returns:
        None.
    """
    SQLModel.metadata.create_all(engine)
    _migrate_timer_table()


def _migrate_timer_table() -> None:
    """
    Upgrade legacy timer tables to support stopwatch rows.

    Returns:
        None.
    """
    if _sqlite_path(settings.database_url) is None:
        return

    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(timer)")).fetchall()
        if not rows:
            return
        column_names = {row[1] for row in rows}
        due_at_nullable = any(row[1] == "due_at" and row[3] == 0 for row in rows)
        if "kind" in column_names and due_at_nullable:
            return

        conn.execute(
            text(
                """
                CREATE TABLE timer_new (
                    id INTEGER PRIMARY KEY,
                    kind VARCHAR NOT NULL DEFAULT 'countdown',
                    label VARCHAR NOT NULL,
                    due_at DATETIME,
                    created_at DATETIME NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO timer_new (id, kind, label, due_at, created_at)
                SELECT id, 'countdown', label, due_at, created_at
                FROM timer
                """
            )
        )
        conn.execute(text("DROP TABLE timer"))
        conn.execute(text("ALTER TABLE timer_new RENAME TO timer"))
