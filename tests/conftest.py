import tempfile
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

import app.memory.db as db
from app.assistant.pending import pending_interactions
from app.memory import models  # noqa: F401
from app.runtime.activity import activity


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr("app.memory.db.engine", engine)
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def reset_runtime_state() -> None:
    activity.reset()
    pending_interactions.reset()


@pytest.fixture(autouse=True)
def disable_background_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.main.register_jobs", lambda: None)
    monkeypatch.setattr("app.main.scheduler.start", lambda: None)
    monkeypatch.setattr("app.main.scheduler.shutdown", lambda wait=False: None)


@pytest.fixture(autouse=True)
def disable_uvicorn_reload_in_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NANO_UVICORN_RELOAD", raising=False)


@pytest.fixture
def api_client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        yield client


def pytest_configure(config) -> None:
    if config.option.basetemp is None:
        base = Path(tempfile.gettempdir()) / "nano-core-pytest"
        base.mkdir(exist_ok=True)
        config.option.basetemp = str(base)
