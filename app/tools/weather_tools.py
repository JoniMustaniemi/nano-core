from __future__ import annotations

from typing import Any

from app.integrations.weather import (
    WeatherApiError,
    WeatherLocationRequiredError,
    format_current_weather,
    get_current_weather_for_store,
)
from app.tools.base import ToolSpec
from app.tools.registry import register_tool


def _get_current_weather(args: dict[str, Any]) -> str:
    """
    Report current weather for the last reported client location.

    Args:
        args: Tool argument dictionary (unused).

    Returns:
        Human-readable current weather summary.
    """
    del args
    try:
        weather = get_current_weather_for_store()
    except WeatherLocationRequiredError:
        return (
            "I do not have a location yet. Open the Nano UI and allow browser "
            "location access so I can check the weather."
        )
    except WeatherApiError:
        return "I could not reach the weather service right now. Try again in a moment."
    return format_current_weather(weather)


register_tool(
    ToolSpec(
        name="get_current_weather",
        description="report current weather at the last reported client location.",
        args_schema={},
        handler=_get_current_weather,
        announcement="Checking the weather.",
        keywords=(
            "weather",
            "temperature",
            "forecast",
            "rain",
            "how hot",
            "how cold",
            "is it raining",
        ),
        ui_label="Current weather",
        ui_message="What's the weather?",
        ui_category="Weather",
        ui_description="Check current weather at your location.",
    )
)
