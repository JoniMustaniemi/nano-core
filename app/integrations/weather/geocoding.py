from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings

BIGDATACLOUD_REVERSE_GEOCODE_URL = "https://api.bigdatacloud.net/data/reverse-geocode-client"


def _pick_place_name(payload: dict[str, Any]) -> str | None:
    for key in ("city", "locality", "principalSubdivision"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def resolve_place_name(latitude: float, longitude: float) -> str | None:
    """Resolve a Finnish place name for the given coordinates."""
    settings = get_settings()
    params: dict[str, str | float] = {
        "latitude": latitude,
        "longitude": longitude,
        "localityLanguage": "fi",
    }
    try:
        response = httpx.get(
            BIGDATACLOUD_REVERSE_GEOCODE_URL,
            params=params,
            timeout=settings.weather_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError, TypeError):
        return None

    if not isinstance(payload, dict):
        return None
    return _pick_place_name(payload)
