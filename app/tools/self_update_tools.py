from __future__ import annotations

from typing import Any

from app.tools.base import ToolSpec
from app.tools.registry import register_tool
from app.tools.self_update_service import SelfUpdateService


def _apply_updates_and_restart(_args: dict[str, Any]) -> str:
  return SelfUpdateService().run().to_json()


register_tool(
  ToolSpec(
    name="apply_updates_and_restart",
    description="pull the latest changes from the main branch; uvicorn reloads app/ changes in dev mode.",
    args_schema={},
    handler=_apply_updates_and_restart,
  )
)
