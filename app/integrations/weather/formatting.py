from __future__ import annotations

from typing import Any

_WMO_CONDITIONS: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    56: "Light freezing drizzle",
    57: "Freezing drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Freezing rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Light rain showers",
    81: "Rain showers",
    82: "Heavy rain showers",
    85: "Light snow showers",
    86: "Snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with heavy hail",
}


def weather_code_to_condition(code: int) -> str:
    """Map an Open-Meteo WMO weather code to a short label."""
    return _WMO_CONDITIONS.get(code, "Unknown conditions")


def format_current_weather(weather: dict[str, Any]) -> str:
    """Format normalized weather data for assistant-facing replies."""
    temperature = weather.get("temperature_c")
    condition = weather.get("condition", "Unknown conditions")
    wind_speed = weather.get("wind_speed_kmh")

    parts: list[str] = []
    if isinstance(temperature, (int, float)):
        parts.append(f"{temperature:.0f}°C")
    parts.append(str(condition))
    if isinstance(wind_speed, (int, float)):
        parts.append(f"wind {wind_speed:.0f} km/h")
    return ", ".join(parts)
