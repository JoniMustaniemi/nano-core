from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.runtime.location import location_store
from app.tools.registry import get_tool


def test_get_current_weather_tool_without_location() -> None:
    tool = get_tool("get_current_weather")
    assert tool is not None
    result = tool.handler({})
    assert "do not have a location" in result.lower()


def test_get_current_weather_tool_returns_formatted_weather(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.integrations.weather.geocoding.resolve_place_name",
        lambda lat, lon: "Helsinki",
    )
    location_store.update(60.17, 24.94)
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "current": {
            "temperature_2m": 12.0,
            "weather_code": 0,
            "wind_speed_10m": 5.0,
        },
    }
    monkeypatch.setattr(
        "app.integrations.weather.client.httpx.get",
        lambda *args, **kwargs: response,
    )

    tool = get_tool("get_current_weather")
    assert tool is not None
    result = tool.handler({})
    assert "Helsinki" in result
    assert "12°C" in result
    assert "Selkeä taivas" in result
    assert "tuuli 5 km/h" in result
