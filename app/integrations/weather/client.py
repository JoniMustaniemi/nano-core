from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import get_settings
from app.integrations.weather.formatting import weather_code_to_condition

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class WeatherLocationRequiredError(Exception):
    """Raised when weather is requested before a location has been reported."""


class WeatherApiError(Exception):
    """Raised when the weather provider request fails."""


def _normalize_current_weather(
    payload: dict[str, Any],
    *,
    latitude: float,
    longitude: float,
) -> dict[str, Any]:
    current = payload.get("current")
    if not isinstance(current, dict):
        raise WeatherApiError("Weather provider returned an unexpected response.")

    temperature = current.get("temperature_2m")
    weather_code = current.get("weather_code")
    wind_speed = current.get("wind_speed_10m")

    if not isinstance(temperature, (int, float)):
        raise WeatherApiError("Weather provider did not return a temperature.")
    if not isinstance(weather_code, int):
        raise WeatherApiError("Weather provider did not return a weather code.")

    condition = weather_code_to_condition(weather_code)
    normalized: dict[str, Any] = {
        "temperature_c": float(temperature),
        "weather_code": weather_code,
        "condition": condition,
        "latitude": latitude,
        "longitude": longitude,
        "fetched_at": datetime.now(UTC).isoformat(),
    }
    if isinstance(wind_speed, (int, float)):
        normalized["wind_speed_kmh"] = float(wind_speed)
    return normalized


def fetch_current_weather(latitude: float, longitude: float) -> dict[str, Any]:
    """Fetch current weather for the given coordinates from Open-Meteo."""
    settings = get_settings()
    params: dict[str, str | float] = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,weather_code,wind_speed_10m",
        "timezone": "auto",
        "wind_speed_unit": "kmh",
    }
    try:
        response = httpx.get(
            OPEN_METEO_FORECAST_URL,
            params=params,
            timeout=settings.weather_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        raise WeatherApiError("Could not reach the weather service.") from exc

    if not isinstance(payload, dict):
        raise WeatherApiError("Weather provider returned an unexpected response.")
    return _normalize_current_weather(payload, latitude=latitude, longitude=longitude)


def get_current_weather_for_store() -> dict[str, Any]:
    """Fetch current weather using coordinates from the runtime location store."""
    from app.runtime.location import location_store

    coordinates = location_store.get_coordinates()
    if coordinates is None:
        raise WeatherLocationRequiredError(
            "Location has not been reported yet. Open the Nano UI and allow location access."
        )
    latitude, longitude = coordinates
    return fetch_current_weather(latitude, longitude)
