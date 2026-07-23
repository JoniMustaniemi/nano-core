from __future__ import annotations

from typing import Any

from app.llm.factory import get_llm_client
from app.tools.base import ToolSpec
from app.tools.pr_service import PullRequestService
from app.tools.registry import register_tool


def _create_pull_request(args: dict[str, Any]) -> str:
    """
    Create a pull request for current workspace changes.

    Args:
        args: Tool argument dictionary (unused in phase 1).

    Returns:
        JSON-encoded pull request result.
    """
    _ = args
    client = get_llm_client()
    result = PullRequestService().run(client=client)
    return result.to_json()


register_tool(
    ToolSpec(
        name="create_pull_request",
        description=(
            "Verify the project passes tests, inspect current changes, name the work in snake_case "
            "using the local model, create feature/<slug>, commit, push, and open a GitHub pull request."
        ),
        args_schema={},
        handler=_create_pull_request,
        announcement="Opening a pull request.",
        keywords=("pull request", "open pr", "create pr", "github pr"),
        ui_label="Create pull request",
        ui_message="Create a pull request.",
        ui_category="GitHub",
        ui_description="Open a PR for current changes.",
    )
)
