from __future__ import annotations

import pytest


def test_post_location_updates_store(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.integrations.weather.geocoding.resolve_place_name",
        lambda lat, lon: "Helsinki",
    )
    response = api_client.post(
        "/api/location",
        json={"latitude": 60.17, "longitude": 24.94, "accuracy_m": 25.0},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["latitude"] == 60.17
    assert payload["longitude"] == 24.94
    assert payload["accuracy_m"] == 25.0
    assert payload["source"] == "browser"
    assert payload["place_name"] == "Helsinki"
    assert payload["updated_at"]


def test_get_location_returns_snapshot(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.integrations.weather.geocoding.resolve_place_name",
        lambda lat, lon: "Berlin",
    )
    api_client.post("/api/location", json={"latitude": 52.52, "longitude": 13.41})

    response = api_client.get("/api/location")
    assert response.status_code == 200
    payload = response.json()
    assert payload["latitude"] == 52.52
    assert payload["longitude"] == 13.41
    assert payload["place_name"] == "Berlin"


def test_get_location_returns_404_when_unset(api_client) -> None:
    response = api_client.get("/api/location")
    assert response.status_code == 404


def test_post_location_validates_latitude(api_client) -> None:
    response = api_client.post(
        "/api/location",
        json={"latitude": 120.0, "longitude": 24.94},
    )
    assert response.status_code == 422


def test_status_snapshot_includes_location(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.integrations.weather.geocoding.resolve_place_name",
        lambda lat, lon: "Helsinki",
    )
    api_client.post("/api/location", json={"latitude": 60.17, "longitude": 24.94})

    response = api_client.get("/api/status")
    assert response.status_code == 200
    location = response.json()["location"]
    assert location["latitude"] == 60.17
    assert location["longitude"] == 24.94
    assert location["place_name"] == "Helsinki"
