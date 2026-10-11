from datetime import UTC, datetime

from sqlmodel import Session

import app.memory.db as db
from app.memory import repository
from app.memory.models import Timer
from app.memory.repository import STOPWATCH_KIND
from app.timers.clock import resolve_stopwatch_started_at, resolve_timer_start_time
from app.timers.serialization import serialize_stopwatch_by_id


def test_resolve_stopwatch_started_at_replaces_epoch() -> None:
    now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    fixed = resolve_stopwatch_started_at(datetime(1970, 1, 1, tzinfo=UTC), now=now)
    assert fixed == now


def test_resolve_timer_start_time_prefers_client_start() -> None:
    client_start = datetime(2026, 6, 1, 10, 0, 0, tzinfo=UTC)
    resolved = resolve_timer_start_time(client_start)
    assert resolved == client_start


def test_serialize_stopwatch_by_id_repairs_epoch_row(monkeypatch) -> None:
    with Session(db.get_engine()) as session:
        timer = Timer(
            label="Lap",
            kind=STOPWATCH_KIND,
            created_at=datetime(1970, 1, 1, tzinfo=UTC),
        )
        session.add(timer)
        session.commit()
        session.refresh(timer)
        stopwatch_id = timer.id

    assert stopwatch_id is not None
    fixed_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)

    class FakeDateTime:
        UTC = UTC

        @classmethod
        def now(cls, tz=None):
            return fixed_now

    monkeypatch.setattr("app.timers.serialization.datetime", FakeDateTime)
    payload = serialize_stopwatch_by_id(stopwatch_id)
    assert payload is not None
    assert payload["started_at"] == fixed_now.isoformat()
    assert payload["elapsed_seconds"] == 0
    repository.delete_timer(stopwatch_id)
