from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.runtime.location import location_store


def test_current_weather_requires_location(api_client) -> None:
    response = api_client.get("/api/weather/current")
    assert response.status_code == 422
    assert "Location has not been reported" in response.json()["detail"]


def test_current_weather_returns_normalized_payload(
    api_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    location_store.update(60.17, 24.94)
    location_store._state.place_name = "Helsinki"
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "current": {
            "temperature_2m": 18.0,
            "weather_code": 2,
            "wind_speed_10m": 8.0,
        },
    }
    monkeypatch.setattr(
        "app.integrations.weather.client.httpx.get",
        lambda *args, **kwargs: response,
    )

    api_response = api_client.get("/api/weather/current")
    assert api_response.status_code == 200
    payload = api_response.json()
    assert payload["temperature_c"] == 18.0
    assert payload["weather_code"] == 2
    assert payload["condition"] == "Puolipilvistä"
    assert payload["wind_speed_kmh"] == 8.0
    assert payload["latitude"] == 60.17
    assert payload["longitude"] == 24.94
    assert payload["location_name"] == "Helsinki"
    assert payload["display"] == "Helsinki · 18°C · Puolipilvistä"
    assert payload["fetched_at"]


def test_current_weather_returns_502_on_provider_error(
    api_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    location_store.update(60.17, 24.94)
    import httpx

    def raise_error(*args, **kwargs):
        raise httpx.HTTPError("down")

    monkeypatch.setattr("app.integrations.weather.client.httpx.get", raise_error)

    response = api_client.get("/api/weather/current")
    assert response.status_code == 502


def test_current_weather_returns_502_on_malformed_provider_json(
    api_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    location_store.update(60.17, 24.94)
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.side_effect = ValueError("invalid json")
    monkeypatch.setattr(
        "app.integrations.weather.client.httpx.get",
        lambda *args, **kwargs: response,
    )

    api_response = api_client.get("/api/weather/current")
    assert api_response.status_code == 502
