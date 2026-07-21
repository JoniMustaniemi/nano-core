import json
from types import SimpleNamespace

import pytest

from app.tools import get_tool


def test_create_pull_request_tool_registered() -> None:
    tool = get_tool("create_pull_request")

    assert tool is not None
    assert tool.args_schema == {}


def test_create_pull_request_tool_delegates_to_service(monkeypatch: pytest.MonkeyPatch) -> None:
    tool = get_tool("create_pull_request")
    assert tool is not None

    monkeypatch.setattr(
        "app.tools.github_tools.get_llm_client",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "app.tools.github_tools.PullRequestService",
        lambda: SimpleNamespace(
            run=lambda client: SimpleNamespace(
                to_json=lambda: json.dumps({"ok": True, "step": "complete", "url": "https://x"})
            )
        ),
    )

    result = tool.handler({})

    assert json.loads(result)["ok"] is True
