from datetime import UTC, datetime, timedelta

import pytest

from app.memory.codebase_index import (
    list_records_for_selection,
    pick_next_scan_target,
    sync_paths,
    upsert_scan_result,
)
from app.memory.db import create_db_and_tables
from app.memory.models import CodebaseFileRecord
from app.proactive.codebase_files import file_content_hash


@pytest.fixture
def codebase_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'codebase_index.sqlite3'}")
    create_db_and_tables()
    yield tmp_path


def test_sync_paths_creates_records(codebase_db, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("a", encoding="utf-8")

    sync_paths(["app/main.py"])

    records = list_records_for_selection(limit=10)
    assert records == []


def test_pick_next_scan_target_prefers_unscanned_file(codebase_db, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app" / "api").mkdir(parents=True)
    (tmp_path / "app" / "tools").mkdir(parents=True)
    (tmp_path / "app" / "api" / "chat.py").write_text("api", encoding="utf-8")
    (tmp_path / "app" / "tools" / "timer.py").write_text("tools", encoding="utf-8")

    all_paths = ["app/api/chat.py", "app/tools/timer.py"]
    first = pick_next_scan_target(all_paths=all_paths)
    assert first in all_paths

    upsert_scan_result(
        path=first,
        content_hash=file_content_hash(first),
        summary="summary",
        last_suggestion=None,
        last_confidence="low",
    )

    second = pick_next_scan_target(all_paths=all_paths)
    assert second in all_paths
    assert second != first


def test_pick_next_scan_target_skips_unchanged_file(codebase_db, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("stable", encoding="utf-8")

    path = "app/main.py"
    upsert_scan_result(
        path=path,
        content_hash=file_content_hash(path),
        summary="already scanned",
        last_suggestion=None,
        last_confidence="low",
    )

    assert pick_next_scan_target(all_paths=[path]) is None


def test_pick_next_scan_target_rescans_changed_file(codebase_db, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app").mkdir()
    target = tmp_path / "app" / "main.py"
    target.write_text("version-1", encoding="utf-8")

    path = "app/main.py"
    upsert_scan_result(
        path=path,
        content_hash="stale-hash",
        summary="old",
        last_suggestion=None,
        last_confidence="low",
        scanned_at=datetime.now(UTC) - timedelta(days=1),
    )

    assert pick_next_scan_target(all_paths=[path]) == path


def test_list_records_for_selection_returns_scanned_records(codebase_db) -> None:
    upsert_scan_result(
        path="app/main.py",
        content_hash="abc",
        summary="main module",
        last_suggestion=None,
        last_confidence="low",
    )

    records = list_records_for_selection(limit=5)

    assert len(records) == 1
    assert isinstance(records[0], CodebaseFileRecord)
    assert records[0].path == "app/main.py"
    assert records[0].summary == "main module"
