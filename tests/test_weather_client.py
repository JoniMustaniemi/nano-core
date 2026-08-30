from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.integrations.weather import WeatherLocationRequiredError
from app.integrations.weather.client import (
    WeatherApiError,
    fetch_current_weather,
    get_current_weather_for_store,
)
from app.integrations.weather.formatting import format_current_weather, weather_code_to_condition
from app.runtime.location import location_store


def test_weather_code_to_condition_known_codes() -> None:
    assert weather_code_to_condition(0) == "Clear sky"
    assert weather_code_to_condition(2) == "Partly cloudy"
    assert weather_code_to_condition(95) == "Thunderstorm"


def test_weather_code_to_condition_unknown_code() -> None:
    assert weather_code_to_condition(123) == "Unknown conditions"


def test_format_current_weather() -> None:
    text = format_current_weather(
        {
            "temperature_c": 18.2,
            "condition": "Partly cloudy",
            "wind_speed_kmh": 12.4,
        }
    )
    assert text == "18°C, Partly cloudy, wind 12 km/h"


def test_format_current_weather_without_wind() -> None:
    text = format_current_weather(
        {
            "temperature_c": 5.0,
            "condition": "Clear sky",
        }
    )
    assert text == "5°C, Clear sky"


def test_fetch_current_weather_normalizes_response(monkeypatch: pytest.MonkeyPatch) -> None:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "current": {
            "temperature_2m": 18.2,
            "weather_code": 2,
            "wind_speed_10m": 12.4,
        },
    }
    monkeypatch.setattr(
        "app.integrations.weather.client.httpx.get",
        lambda *args, **kwargs: response,
    )

    weather = fetch_current_weather(52.52, 13.41)

    assert weather["temperature_c"] == 18.2
    assert weather["weather_code"] == 2
    assert weather["condition"] == "Partly cloudy"
    assert weather["wind_speed_kmh"] == 12.4
    assert weather["latitude"] == 52.52
    assert weather["longitude"] == 13.41
    assert weather["fetched_at"]


def test_fetch_current_weather_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    def raise_error(*args, **kwargs):
        raise httpx.HTTPError("network down")

    monkeypatch.setattr("app.integrations.weather.client.httpx.get", raise_error)

    with pytest.raises(WeatherApiError, match="Could not reach the weather service"):
        fetch_current_weather(52.52, 13.41)


def test_get_current_weather_for_store_requires_location() -> None:
    with pytest.raises(WeatherLocationRequiredError):
        get_current_weather_for_store()


def test_get_current_weather_for_store_uses_location(monkeypatch: pytest.MonkeyPatch) -> None:
    location_store.update(60.17, 24.94)
    monkeypatch.setattr(
        "app.integrations.weather.client.fetch_current_weather",
        lambda lat, lon: {"temperature_c": 10.0, "latitude": lat, "longitude": lon},
    )

    weather = get_current_weather_for_store()

    assert weather["latitude"] == 60.17
    assert weather["longitude"] == 24.94
