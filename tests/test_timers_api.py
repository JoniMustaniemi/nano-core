from datetime import UTC, datetime, timedelta

from starlette.testclient import TestClient

from app.memory import repository
from app.runtime.snapshot import build_runtime_snapshot


def test_patch_timer_updates_label_and_status(api_client: TestClient) -> None:
    due_at = datetime.now(UTC) + timedelta(minutes=5)
    timer = repository.add_timer("Tea", due_at)
    assert timer.id is not None

    response = api_client.patch(f"/api/timers/{timer.id}", json={"label": "Pizza"})
    status = api_client.get("/api/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == timer.id
    assert payload["label"] == "Pizza"
    assert payload["due_at"] == due_at.isoformat()
    assert status.json()["active_timers"][0]["label"] == "Pizza"


def test_patch_stopwatch_updates_label(api_client: TestClient) -> None:
    started_at = datetime.now(UTC) - timedelta(seconds=20)
    stopwatch = repository.add_stopwatch("Lap", started_at=started_at)
    assert stopwatch.id is not None

    response = api_client.patch(f"/api/stopwatches/{stopwatch.id}", json={"label": "Run"})
    snapshot = build_runtime_snapshot()

    assert response.status_code == 200
    assert response.json()["label"] == "Run"
    active_stopwatches = snapshot["active_stopwatches"]
    assert isinstance(active_stopwatches, list)
    assert active_stopwatches[0]["label"] == "Run"
    assert active_stopwatches[0]["started_at"] == started_at.isoformat()


def test_patch_timer_returns_404_for_missing_or_wrong_kind(api_client: TestClient) -> None:
    stopwatch = repository.add_stopwatch("Lap")
    assert stopwatch.id is not None

    missing = api_client.patch("/api/timers/99999", json={"label": "Pizza"})
    wrong_kind = api_client.patch(f"/api/timers/{stopwatch.id}", json={"label": "Pizza"})

    assert missing.status_code == 404
    assert wrong_kind.status_code == 404


def test_patch_timer_rejects_invalid_label(api_client: TestClient) -> None:
    timer = repository.add_timer("Tea", datetime.now(UTC) + timedelta(minutes=5))
    assert timer.id is not None

    response = api_client.patch(
        f"/api/timers/{timer.id}",
        json={"label": "x" * 65},
    )

    assert response.status_code == 400
    assert "64 characters" in response.json()["detail"]
