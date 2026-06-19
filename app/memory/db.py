from pathlib import Path

from sqlmodel import SQLModel, create_engine

from app.config import get_settings


def _sqlite_path(database_url: str) -> Path | None:
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
    SQLModel.metadata.create_all(engine)
