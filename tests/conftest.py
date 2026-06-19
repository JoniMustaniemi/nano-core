from pathlib import Path

import pytest
from sqlmodel import create_engine

import app.memory.db as db
from app.runtime.activity import activity


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.sqlite3'}")
    monkeypatch.setattr(db, "engine", engine)
    db.create_db_and_tables()


@pytest.fixture(autouse=True)
def reset_activity() -> None:
    activity.reset()
