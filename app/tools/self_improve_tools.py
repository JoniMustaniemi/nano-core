from __future__ import annotations

from typing import Any

from app.assistant.llm_factory import get_llm_client
from app.tools.base import ToolSpec
from app.tools.registry import register_tool
from app.tools.self_improve_service import SelfImproveService


def _propose_self_changes(args: dict[str, Any]) -> str:
  goal = str(args.get("goal", "")).strip()
  if not goal:
    return SelfImproveService().run(client=get_llm_client(), goal="general improvement").to_json()
  return SelfImproveService().run(client=get_llm_client(), goal=goal).to_json()


register_tool(
  ToolSpec(
    name="propose_self_changes",
    description="analyze Nano's codebase, apply improvements under app/, verify, and open a pull request.",
    args_schema={"goal": "What to improve in Nano's own code."},
    handler=_propose_self_changes,
  )
)
