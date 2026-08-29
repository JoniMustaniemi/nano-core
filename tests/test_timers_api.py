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


def test_delete_timer_removes_only_requested_timer(api_client: TestClient) -> None:
    due_at = datetime.now(UTC) + timedelta(minutes=5)
    timer_one = repository.add_timer("One", due_at)
    timer_two = repository.add_timer("Two", due_at + timedelta(minutes=1))
    timer_three = repository.add_timer("Three", due_at + timedelta(minutes=2))
    assert timer_one.id is not None
    assert timer_two.id is not None
    assert timer_three.id is not None

    response = api_client.delete(f"/api/timers/{timer_two.id}")
    status = api_client.get("/api/status")

    assert response.status_code == 204
    active_ids = [timer["id"] for timer in status.json()["active_timers"]]
    assert active_ids == [timer_one.id, timer_three.id]


def test_delete_timer_returns_404_for_missing_or_wrong_kind(api_client: TestClient) -> None:
    stopwatch = repository.add_stopwatch("Lap")
    assert stopwatch.id is not None

    missing = api_client.delete("/api/timers/99999")
    wrong_kind = api_client.delete(f"/api/timers/{stopwatch.id}")

    assert missing.status_code == 404
    assert wrong_kind.status_code == 404


def test_delete_timer_unschedules_completion_job(api_client: TestClient) -> None:
    from app.scheduler.jobs import _timer_job_id, schedule_timer, scheduler

    due_at = datetime.now(UTC) + timedelta(minutes=5)
    timer = repository.add_timer("Tea", due_at)
    assert timer.id is not None
    schedule_timer(timer.id, due_at)
    assert scheduler.get_job(_timer_job_id(timer.id)) is not None

    response = api_client.delete(f"/api/timers/{timer.id}")

    assert response.status_code == 204
    assert repository.list_timers() == []
    assert scheduler.get_job(_timer_job_id(timer.id)) is None


def test_delete_stopwatch_removes_only_requested_stopwatch(api_client: TestClient) -> None:
    stopwatch_one = repository.add_stopwatch("One")
    stopwatch_two = repository.add_stopwatch("Two")
    stopwatch_three = repository.add_stopwatch("Three")
    assert stopwatch_one.id is not None
    assert stopwatch_two.id is not None
    assert stopwatch_three.id is not None

    response = api_client.delete(f"/api/stopwatches/{stopwatch_two.id}")
    status = api_client.get("/api/status")

    assert response.status_code == 204
    active_ids = [stopwatch["id"] for stopwatch in status.json()["active_stopwatches"]]
    assert active_ids == [stopwatch_one.id, stopwatch_three.id]


def test_delete_stopwatch_returns_404_for_missing_or_wrong_kind(api_client: TestClient) -> None:
    timer = repository.add_timer("Tea", datetime.now(UTC) + timedelta(minutes=5))
    assert timer.id is not None

    missing = api_client.delete("/api/stopwatches/99999")
    wrong_kind = api_client.delete(f"/api/stopwatches/{timer.id}")

    assert missing.status_code == 404
    assert wrong_kind.status_code == 404


def test_delete_stopwatch_does_not_affect_countdown_timers(api_client: TestClient) -> None:
    due_at = datetime.now(UTC) + timedelta(minutes=5)
    timer = repository.add_timer("Tea", due_at)
    stopwatch = repository.add_stopwatch("Lap")
    assert timer.id is not None
    assert stopwatch.id is not None

    response = api_client.delete(f"/api/stopwatches/{stopwatch.id}")
    status = api_client.get("/api/status")

    assert response.status_code == 204
    assert status.json()["active_stopwatches"] == []
    assert len(status.json()["active_timers"]) == 1
    assert status.json()["active_timers"][0]["id"] == timer.id
