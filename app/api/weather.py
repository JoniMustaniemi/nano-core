from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.integrations.weather import (
    WeatherApiError,
    WeatherLocationRequiredError,
    get_current_weather_for_store,
)

router = APIRouter(prefix="/weather", tags=["weather"])


class CurrentWeatherResponse(BaseModel):
    temperature_c: float
    weather_code: int
    condition: str
    wind_speed_kmh: float | None = None
    latitude: float
    longitude: float
    fetched_at: str


@router.get("/current")
def current_weather() -> CurrentWeatherResponse:
    """Return current weather for the last reported client location."""
    try:
        weather = get_current_weather_for_store()
    except WeatherLocationRequiredError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except WeatherApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return CurrentWeatherResponse(**_response_payload(weather))


def _response_payload(weather: dict[str, Any]) -> dict[str, Any]:
    return {
        "temperature_c": weather["temperature_c"],
        "weather_code": weather["weather_code"],
        "condition": weather["condition"],
        "wind_speed_kmh": weather.get("wind_speed_kmh"),
        "latitude": weather["latitude"],
        "longitude": weather["longitude"],
        "fetched_at": weather["fetched_at"],
    }
