import pytest

from app.runtime.snapshot import build_runtime_snapshot


def test_system_metrics_endpoint(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.system.serialize_system_metrics",
        lambda: {"cpu_temperature_celsius": 45.2, "throttled": False},
    )

    response = api_client.get("/api/system/metrics")

    assert response.status_code == 200
    assert response.json() == {
        "cpu_temperature_celsius": 45.2,
        "throttled": False,
    }


def test_status_snapshot_includes_system_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.runtime.snapshot.serialize_system_metrics",
        lambda: {"cpu_temperature_celsius": 52.0, "throttled": None},
    )

    snapshot = build_runtime_snapshot()

    assert snapshot["system"] == {
        "cpu_temperature_celsius": 52.0,
        "throttled": None,
    }
