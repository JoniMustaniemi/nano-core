import pytest

from app.memory.codebase_index import get_record
from app.memory.db import create_db_and_tables
from app.proactive.codebase_crawl import CodebaseCrawlService


class _CrawlClient:
    def complete(self, messages) -> str:
        return (
            '{"summary": "Timer module handles reminders.", '
            '"suggestion": "Add clearer timer errors.", '
            '"confidence": "medium"}'
        )


class _LowConfidenceClient:
    def complete(self, messages) -> str:
        return (
            '{"summary": "Timer module handles reminders.", '
            '"suggestion": "Maybe refactor later.", '
            '"confidence": "low"}'
        )


@pytest.fixture
def crawl_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'crawl.sqlite3'}")
    create_db_and_tables()
    yield tmp_path


def test_codebase_crawl_returns_offer_and_updates_ledger(crawl_db, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("print('nano')\n", encoding="utf-8")

    monkeypatch.setattr(
        "app.memory.codebase_index.pick_next_scan_target",
        lambda all_paths: "app/main.py",
    )
    monkeypatch.setattr(
        "app.proactive.codebase_crawl.read_text_file",
        lambda path: "print('nano')",
    )
    monkeypatch.setattr(
        "app.proactive.codebase_crawl.file_content_hash",
        lambda path: "hash-main",
    )
    monkeypatch.setattr("app.proactive.codebase_crawl.activity.log", lambda **kwargs: None)

    offer = CodebaseCrawlService().scan_next_file(client=_CrawlClient())

    assert offer is not None
    assert offer.kind == "self_improvement_suggestion"
    assert offer.payload["files"] == ["app/main.py"]

    record = get_record("app/main.py")
    assert record is not None
    assert record.summary == "Timer module handles reminders."
    assert record.last_suggestion == "Add clearer timer errors."


def test_codebase_crawl_skips_offer_on_low_confidence(crawl_db, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("print('nano')\n", encoding="utf-8")

    monkeypatch.setattr(
        "app.memory.codebase_index.pick_next_scan_target",
        lambda all_paths: "app/main.py",
    )
    monkeypatch.setattr(
        "app.proactive.codebase_crawl.read_text_file",
        lambda path: "print('nano')",
    )
    monkeypatch.setattr(
        "app.proactive.codebase_crawl.file_content_hash",
        lambda path: "hash-main",
    )
    monkeypatch.setattr("app.proactive.codebase_crawl.activity.log", lambda **kwargs: None)

    offer = CodebaseCrawlService().scan_next_file(client=_LowConfidenceClient())

    assert offer is None
    record = get_record("app/main.py")
    assert record is not None
    assert record.last_confidence == "low"
