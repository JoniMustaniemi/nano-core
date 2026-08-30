from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.config import get_settings

_SCHEMA_VERSION_TABLE = "schema_migrations"


def run_migrations(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {_SCHEMA_VERSION_TABLE} (
                    version INTEGER PRIMARY KEY
                )
                """
            )
        )
        current_version = conn.execute(
            text(f"SELECT MAX(version) FROM {_SCHEMA_VERSION_TABLE}")
        ).scalar()
        version = int(current_version or 0)

        if version < 1:
            _migrate_timer_stopwatch(conn)
            conn.execute(text(f"INSERT INTO {_SCHEMA_VERSION_TABLE} (version) VALUES (1)"))


def _sqlite_path(database_url: str) -> Path | None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None
    return Path(database_url.removeprefix(prefix))


def _migrate_timer_stopwatch(conn: Connection) -> None:
    settings = get_settings()
    if _sqlite_path(settings.database_url) is None:
        return

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
    conn.execute(text("CREATE INDEX ix_timer_kind ON timer (kind)"))
    conn.execute(text("CREATE INDEX ix_timer_due_at ON timer (due_at)"))
