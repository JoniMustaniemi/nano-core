import tempfile
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

import app.memory.db as db
from app.assistant.pending import pending_interactions
from app.memory import models  # noqa: F401
from app.runtime.activity import activity
from app.runtime.boot_state import boot_store
from app.runtime.location import location_store


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
    monkeypatch.setattr("app.memory.db.get_engine", lambda: engine)
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def reset_runtime_state() -> None:
    activity.reset()
    pending_interactions.reset()
    location_store.reset()
    boot_store.reset()


@pytest.fixture(autouse=True)
def disable_background_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.main.register_jobs", lambda: None)
    monkeypatch.setattr("app.main.scheduler.start", lambda: None)
    monkeypatch.setattr("app.main.scheduler.shutdown", lambda wait=False: None)


@pytest.fixture(autouse=True)
def isolate_google_calendar_credentials(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Point Google Calendar auth files at empty temp paths so tests stay offline."""
    from app.config import get_settings

    credentials_dir = tmp_path_factory.mktemp("google-credentials")
    monkeypatch.setenv("GOOGLE_TOKEN_PATH", str(credentials_dir / "token.json"))
    monkeypatch.setenv("GOOGLE_CREDENTIALS_PATH", str(credentials_dir / "credentials.json"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def isolate_api_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep API routes open in tests unless a case explicitly sets API_KEY."""
    from app.config import get_settings

    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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
