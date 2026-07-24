from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.main import app
from app.memory import improvement_plans, internal_notes
from app.memory.db import create_db_and_tables
from app.proactive.types import ProactiveOffer


def test_improvement_plan_api_list_get_and_process(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'api.sqlite3'}")
    create_db_and_tables()

    plan = improvement_plans.create_plan(
        title="Clearer timer errors",
        goal="clearer timer errors",
        body="Summary\n- improve timer copy",
        files=["app/assistant/flows/timer.py"],
    )
    assert plan.id is not None

    with TestClient(app) as client:
        listed = client.get("/api/improvement-plans")
        assert listed.status_code == 200
        payload = listed.json()
        assert len(payload) == 1
        assert payload[0]["title"] == "Clearer timer errors"
        assert payload[0]["status"] == "pending"
        assert payload[0]["kind"] == "drafted"

        detail = client.get(f"/api/improvement-plans/{plan.id}")
        assert detail.status_code == 200
        assert detail.json()["body"].startswith("Summary")

        processed = client.post(f"/api/improvement-plans/{plan.id}/process")
        assert processed.status_code == 204
        assert processed.content == b""

        assert improvement_plans.get_plan(plan.id) is None
        assert improvement_plans.has_unprocessed_plan() is False

        listed_after = client.get("/api/improvement-plans")
        assert listed_after.status_code == 200
        assert listed_after.json() == []


def test_improvement_plan_api_lists_pending_suggestions(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'suggestions.sqlite3'}")
    create_db_and_tables()

    offer = ProactiveOffer(
        kind="self_improvement_suggestion",
        title="Improve timers",
        summary="Make timer errors clearer.",
        payload={"goal": "clearer timer errors", "files": ["app/assistant/flows/timer.py"]},
        created_at=datetime.now(UTC),
    )
    note = internal_notes.add_internal_note(
        kind=offer.kind,
        title=offer.title,
        content=offer.summary,
        payload_json=offer.to_json(),
        next_attempt_at=datetime.now(UTC),
    )
    assert note.id is not None

    with TestClient(app) as client:
        listed = client.get("/api/improvement-plans")
        assert listed.status_code == 200
        payload = listed.json()
        assert len(payload) == 1
        assert payload[0]["id"] == note.id
        assert payload[0]["status"] == "waiting"
        assert payload[0]["kind"] == "suggestion"

        detail = client.get(f"/api/improvement-plans/suggestions/{note.id}")
        assert detail.status_code == 200
        body = detail.json()["body"]
        assert "Make timer errors clearer." in body
        assert "app/assistant/flows/timer.py" in body

        processed = client.post(f"/api/improvement-plans/suggestions/{note.id}/process")
        assert processed.status_code == 204
        assert processed.content == b""
        assert internal_notes.get_internal_note(note.id) is None

        listed_after = client.get("/api/improvement-plans")
        assert listed_after.status_code == 200
        assert listed_after.json() == []


def test_improvement_plan_api_hides_suggestions_when_drafted_plan_pending(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'hide-suggestions.sqlite3'}")
    create_db_and_tables()

    improvement_plans.create_plan(
        title="Existing plan",
        goal="existing",
        body="Summary",
        files=["app/main.py"],
    )
    offer = ProactiveOffer(
        kind="self_improvement_suggestion",
        title="Improve timers",
        summary="Make timer errors clearer.",
        payload={"goal": "clearer timer errors", "files": ["app/assistant/flows/timer.py"]},
        created_at=datetime.now(UTC),
    )
    internal_notes.add_internal_note(
        kind=offer.kind,
        title=offer.title,
        content=offer.summary,
        payload_json=offer.to_json(),
        next_attempt_at=datetime.now(UTC),
    )

    with TestClient(app) as client:
        listed = client.get("/api/improvement-plans")
        assert listed.status_code == 200
        payload = listed.json()
        assert len(payload) == 1
        assert payload[0]["kind"] == "drafted"
        assert payload[0]["status"] == "pending"


def test_record_from_offer_skips_second_suggestion(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'one-suggestion.sqlite3'}")
    create_db_and_tables()

    from app.memory.internal_note_service import InternalNoteService

    offer = ProactiveOffer(
        kind="self_improvement_suggestion",
        title="Improve timers",
        summary="Make timer errors clearer.",
        payload={"goal": "clearer timer errors"},
        created_at=datetime.now(UTC),
    )
    service = InternalNoteService()
    first = service.record_from_offer(offer, next_attempt_at=datetime.now(UTC))
    second = service.record_from_offer(
        ProactiveOffer(
            kind="self_improvement_suggestion",
            title="Other idea",
            summary="Something else.",
            payload={"goal": "other"},
            created_at=datetime.now(UTC),
        ),
        next_attempt_at=datetime.now(UTC),
    )

    assert first is not None
    assert second is None
    assert len(internal_notes.list_pending_self_improvement_notes(limit=10)) == 1
