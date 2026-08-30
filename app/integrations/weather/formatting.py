from __future__ import annotations

from typing import Any

_WMO_CONDITIONS: dict[int, str] = {
    0: "Selkeä taivas",
    1: "Enimmäkseen selkeä",
    2: "Puolipilvistä",
    3: "Pilvistä",
    45: "Usva",
    48: "Huurteinen usva",
    51: "Kevyt tihkusade",
    53: "Tihkusade",
    55: "Voimakas tihkusade",
    56: "Kevyt jäätyvä tihkusade",
    57: "Jäätyvä tihkusade",
    61: "Kevyt sade",
    63: "Sade",
    65: "Voimakas sade",
    66: "Kevyt jääsade",
    67: "Jääsade",
    71: "Kevyt lumisade",
    73: "Lumisade",
    75: "Voimakas lumisade",
    77: "Lumi rakeita",
    80: "Kevyet sadekuurot",
    81: "Sadekuurot",
    82: "Voimakkaat sadekuurot",
    85: "Kevyet lumikuurot",
    86: "Lumikuurot",
    95: "Ukkonen",
    96: "Ukkonen ja rae",
    99: "Ukkonen ja voimakas rae",
}

_UNKNOWN_CONDITION = "Tuntematon sää"


def weather_code_to_condition(code: int) -> str:
    """Map an Open-Meteo WMO weather code to a short Finnish label."""
    return _WMO_CONDITIONS.get(code, _UNKNOWN_CONDITION)


def format_weather_display(weather: dict[str, Any], *, place_name: str | None = None) -> str:
    """Format normalized weather data for the UI weather chip."""
    temperature = weather.get("temperature_c")
    condition = weather.get("condition", _UNKNOWN_CONDITION)

    temp_part = None
    if isinstance(temperature, (int, float)):
        temp_part = f"{temperature:.0f}°C"

    if place_name and temp_part:
        return f"{place_name} · {temp_part} · {condition}"
    if place_name:
        return f"{place_name} · {condition}"
    if temp_part:
        return f"{temp_part} · {condition}"
    return str(condition)


def format_current_weather(weather: dict[str, Any]) -> str:
    """Format normalized weather data for assistant-facing replies."""
    place_name = weather.get("location_name")
    temperature = weather.get("temperature_c")
    condition = weather.get("condition", _UNKNOWN_CONDITION)
    wind_speed = weather.get("wind_speed_kmh")

    parts: list[str] = []
    if isinstance(place_name, str) and place_name.strip():
        parts.append(place_name.strip())
    if isinstance(temperature, (int, float)):
        parts.append(f"{temperature:.0f}°C")
    parts.append(str(condition))
    if isinstance(wind_speed, (int, float)):
        parts.append(f"tuuli {wind_speed:.0f} km/h")
    return ", ".join(parts)
