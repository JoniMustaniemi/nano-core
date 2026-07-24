from pathlib import Path

import pytest
from sqlmodel import create_engine

import app.memory.db as db
from app.assistant.pending import pending_interactions
from app.runtime.activity import activity


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Provide test support for isolated db.

    Args:
        tmp_path: Temporary directory path provided by pytest.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'test.sqlite3'}")
    monkeypatch.setattr(db, "engine", engine)
    db.create_db_and_tables()


@pytest.fixture(autouse=True)
def reset_activity() -> None:
    """
    Provide test support for reset activity.

    Returns:
        None.
    """
    activity.reset()


@pytest.fixture(autouse=True)
def reset_pending_interactions() -> None:
    """
    Provide test support for reset pending interactions.

    Returns:
        None.
    """
    pending_interactions.reset()


@pytest.fixture(autouse=True)
def disable_uvicorn_reload_in_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep dev-server reload env from blocking self-improve in unrelated tests."""
    monkeypatch.delenv("NANO_UVICORN_RELOAD", raising=False)
