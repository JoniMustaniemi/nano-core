from datetime import UTC, datetime

from app.common.types import ProactiveOffer
from app.memory import improvement_plans, internal_notes
from app.memory.internal_note_service import InternalNoteService


def _pass_implement_preflight(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.is_git_repo",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.gh_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.gh_authenticated",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.working_tree_dirty",
        lambda: False,
    )
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.get_open_pull_request",
        lambda: None,
    )


def test_improvement_plan_api_list_get_and_process(api_client) -> None:
    plan = improvement_plans.create_plan(
        title="Clearer timer errors",
        goal="clearer timer errors",
        body="Summary\n- improve timer copy",
        files=["app/assistant/flows/timer.py"],
    )
    assert plan.id is not None

    listed = api_client.get("/api/improvement-plans")
    assert listed.status_code == 200
    payload = listed.json()
    assert len(payload) == 1
    assert payload[0]["title"] == "Clearer timer errors"
    assert payload[0]["status"] == "pending"
    assert payload[0]["kind"] == "drafted"

    detail = api_client.get(f"/api/improvement-plans/{plan.id}")
    assert detail.status_code == 200
    assert detail.json()["body"].startswith("Summary")

    processed = api_client.post(f"/api/improvement-plans/{plan.id}/process")
    assert processed.status_code == 204
    assert processed.content == b""

    assert improvement_plans.get_plan(plan.id) is None
    assert improvement_plans.has_unprocessed_plan() is False

    listed_after = api_client.get("/api/improvement-plans")
    assert listed_after.status_code == 200
    assert listed_after.json() == []


def test_improvement_plan_api_lists_pending_suggestions(api_client) -> None:
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

    listed = api_client.get("/api/improvement-plans")
    assert listed.status_code == 200
    payload = listed.json()
    assert len(payload) == 1
    assert payload[0]["id"] == note.id
    assert payload[0]["status"] == "waiting"
    assert payload[0]["kind"] == "suggestion"

    detail = api_client.get(f"/api/improvement-plans/suggestions/{note.id}")
    assert detail.status_code == 200
    body = detail.json()["body"]
    assert "Make timer errors clearer." in body
    assert "app/assistant/flows/timer.py" in body

    processed = api_client.post(f"/api/improvement-plans/suggestions/{note.id}/process")
    assert processed.status_code == 204
    assert processed.content == b""
    assert internal_notes.get_internal_note(note.id) is None

    listed_after = api_client.get("/api/improvement-plans")
    assert listed_after.status_code == 200
    assert listed_after.json() == []


def test_improvement_plan_api_hides_suggestions_when_drafted_plan_pending(api_client) -> None:
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

    listed = api_client.get("/api/improvement-plans")
    assert listed.status_code == 200
    payload = listed.json()
    assert len(payload) == 1
    assert payload[0]["kind"] == "drafted"
    assert payload[0]["status"] == "pending"


def test_record_from_offer_skips_second_suggestion() -> None:
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


def test_improvement_plan_api_implement_returns_202(monkeypatch, api_client) -> None:
    plan = improvement_plans.create_plan(
        title="Clearer timer errors",
        goal="clearer timer errors",
        body="Summary\nImprove timer copy.",
        files=["app/runtime/status_copy.py"],
    )
    assert plan.id is not None
    _pass_implement_preflight(monkeypatch)
    monkeypatch.setattr(
        "app.tools.improvement_plan_facade.run_background",
        lambda fn, *, label: fn(),
    )
    monkeypatch.setattr(
        "app.tools.improvement_plan_facade.ImprovementPlanImplementationService.run",
        lambda self, plan_id: None,
    )

    response = api_client.post(f"/api/improvement-plans/{plan.id}/implement")

    assert response.status_code == 202
    payload = response.json()
    assert payload == {"ok": True, "plan_id": plan.id, "status": "implementing"}
    saved = improvement_plans.get_plan(plan.id)
    assert saved is not None
    assert saved.status == "implementing"
    assert improvement_plans.has_unprocessed_plan() is True


def test_improvement_plan_api_implement_returns_404(api_client) -> None:
    response = api_client.post("/api/improvement-plans/999/implement")
    assert response.status_code == 404


def test_improvement_plan_api_implement_returns_409_when_not_pending(api_client) -> None:
    plan = improvement_plans.create_plan(
        title="Clearer timer errors",
        goal="clearer timer errors",
        body="Summary\nImprove timer copy.",
        files=["app/runtime/status_copy.py"],
    )
    assert plan.id is not None
    improvement_plans.try_mark_implementing(plan.id)

    response = api_client.post(f"/api/improvement-plans/{plan.id}/implement")
    assert response.status_code == 409


def test_improvement_plan_api_implement_returns_400_for_dirty_tree(monkeypatch, api_client) -> None:
    plan = improvement_plans.create_plan(
        title="Clearer timer errors",
        goal="clearer timer errors",
        body="Summary\nImprove timer copy.",
        files=["app/runtime/status_copy.py"],
    )
    assert plan.id is not None
    _pass_implement_preflight(monkeypatch)
    monkeypatch.setattr(
        "app.tools.improvement_plan_implementation.working_tree_dirty",
        lambda: True,
    )

    response = api_client.post(f"/api/improvement-plans/{plan.id}/implement")
    assert response.status_code == 400
    assert "uncommitted changes" in response.json()["detail"].lower()
    saved = improvement_plans.get_plan(plan.id)
    assert saved is not None
    assert saved.status == "pending"
