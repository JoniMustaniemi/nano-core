from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.integrations.weather import WeatherLocationRequiredError
from app.integrations.weather.client import (
    WeatherApiError,
    fetch_current_weather,
    get_current_weather_for_store,
)
from app.integrations.weather.formatting import (
    format_current_weather,
    format_weather_display,
    weather_code_to_condition,
)
from app.runtime.location import location_store


def test_weather_code_to_condition_known_codes() -> None:
    assert weather_code_to_condition(0) == "Selkeä taivas"
    assert weather_code_to_condition(2) == "Puolipilvistä"
    assert weather_code_to_condition(95) == "Ukkonen"


def test_weather_code_to_condition_unknown_code() -> None:
    assert weather_code_to_condition(123) == "Tuntematon sää"


def test_format_weather_display_with_location() -> None:
    text = format_weather_display(
        {
            "temperature_c": 20.0,
            "condition": "Pilvistä",
        },
        place_name="Helsinki",
    )
    assert text == "Helsinki · 20°C · Pilvistä"


def test_format_weather_display_without_location() -> None:
    text = format_weather_display(
        {
            "temperature_c": 20.0,
            "condition": "Pilvistä",
        },
    )
    assert text == "20°C · Pilvistä"


def test_format_current_weather() -> None:
    text = format_current_weather(
        {
            "location_name": "Helsinki",
            "temperature_c": 18.2,
            "condition": "Puolipilvistä",
            "wind_speed_kmh": 12.4,
        }
    )
    assert text == "Helsinki, 18°C, Puolipilvistä, tuuli 12 km/h"


def test_format_current_weather_without_wind() -> None:
    text = format_current_weather(
        {
            "location_name": "Helsinki",
            "temperature_c": 5.0,
            "condition": "Selkeä taivas",
        }
    )
    assert text == "Helsinki, 5°C, Selkeä taivas"


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
    assert weather["condition"] == "Puolipilvistä"
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


def test_fetch_current_weather_raises_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.side_effect = ValueError("invalid json")
    monkeypatch.setattr(
        "app.integrations.weather.client.httpx.get",
        lambda *args, **kwargs: response,
    )

    with pytest.raises(WeatherApiError, match="unexpected response"):
        fetch_current_weather(52.52, 13.41)


def test_fetch_current_weather_accepts_float_weather_code(monkeypatch: pytest.MonkeyPatch) -> None:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "current": {
            "temperature_2m": 18.0,
            "weather_code": 2.0,
            "wind_speed_10m": 8.0,
        },
    }
    monkeypatch.setattr(
        "app.integrations.weather.client.httpx.get",
        lambda *args, **kwargs: response,
    )

    weather = fetch_current_weather(52.52, 13.41)

    assert weather["weather_code"] == 2
    assert weather["condition"] == "Puolipilvistä"


def test_get_current_weather_for_store_requires_location() -> None:
    with pytest.raises(WeatherLocationRequiredError):
        get_current_weather_for_store()


def test_get_current_weather_for_store_uses_location(monkeypatch: pytest.MonkeyPatch) -> None:
    location_store.update(60.17, 24.94)
    location_store._state.place_name = "Helsinki"
    monkeypatch.setattr(
        "app.integrations.weather.client.fetch_current_weather",
        lambda lat, lon: {
            "temperature_c": 10.0,
            "weather_code": 0,
            "condition": "Selkeä taivas",
            "latitude": lat,
            "longitude": lon,
            "fetched_at": "2026-01-01T00:00:00+00:00",
        },
    )

    weather = get_current_weather_for_store()

    assert weather["latitude"] == 60.17
    assert weather["longitude"] == 24.94
    assert weather["location_name"] == "Helsinki"
