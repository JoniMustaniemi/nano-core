from __future__ import annotations

import json
from typing import Any

from app.health import run_health_checks
from app.tools.base import ToolSpec
from app.tools.registry import register_tool


def _check_health(args: dict[str, Any]) -> str:
    """
    Check health.

    Args:
        args: Tool argument dictionary.

    Returns:
        Generated or formatted string value.
    """
    del args
    results = run_health_checks()
    if not results:
        return json.dumps({"overall": "unknown", "checks": []}, indent=2)

    overall_ok = all(result.ok for result in results)
    payload = {
        "overall": "ok" if overall_ok else "error",
        "checks": [
            {
                "name": result.name,
                "status": "ok" if result.ok else "error",
                "detail": result.detail,
            }
            for result in results
        ],
    }
    return json.dumps(payload, indent=2)


register_tool(
    ToolSpec(
        name="check_health",
        description="check Nano's current health and report any problems.",
        args_schema={},
        handler=_check_health,
        announcement="Running a health diagnostic.",
        keywords=(
            "check your health",
            "health check",
            "run diagnostics",
            "run diagnostic",
            "diagnostic check",
            "diagnostics check",
            "check diagnostics",
            "check diagnostic",
            "check yourself",
            "self check",
            "system check",
        ),
        ui_label="Health check",
        ui_message="Check your health.",
        ui_category="System",
        ui_description="Run Nano diagnostics.",
    )
)
