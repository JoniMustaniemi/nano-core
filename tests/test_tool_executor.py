import json
from types import SimpleNamespace

from app.assistant.tool_executor import ToolExecutor
from app.runtime.status_copy import IMPROVEMENT_PLAN_FAILED_TITLE, failed_tool_title, ran_tool_title


def test_tool_executor_logs_success_only_when_tool_succeeds(monkeypatch) -> None:
    logged: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "app.assistant.tool_executor.activity.working",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "app.assistant.tool_executor.activity.log",
        lambda **kwargs: logged.append((kwargs["title"], kwargs["detail"])),
    )

    class _Runner:
        def execute(self, tool_name, args):
            return SimpleNamespace(
                tool=tool_name,
                content='{"ok": true}',
                ok=True,
            )

    executor = ToolExecutor(tool_runner=_Runner())
    source = executor.run(
        user_message="Improve yourself.",
        conversation_id="default",
        tool_name="draft_improvement_plan",
    )

    assert source.speak is False
    assert logged == [(ran_tool_title("draft_improvement_plan"), "Done.")]


def test_tool_executor_logs_failure_title_when_tool_fails(monkeypatch) -> None:
    logged: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "app.assistant.tool_executor.activity.working",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "app.assistant.tool_executor.activity.log",
        lambda **kwargs: logged.append((kwargs["title"], kwargs["detail"])),
    )

    class _Runner:
        def execute(self, tool_name, args):
            return SimpleNamespace(
                tool=tool_name,
                content=json.dumps(
                    {
                        "ok": False,
                        "step": "preflight",
                        "error": "Workspace is not a git repository.",
                    }
                ),
                ok=False,
            )

    executor = ToolExecutor(tool_runner=_Runner())
    executor.run(
        user_message="Improve yourself.",
        conversation_id="default",
        tool_name="draft_improvement_plan",
    )

    assert logged == [
        (
            failed_tool_title("draft_improvement_plan"),
            "Workspace is not a git repository.",
        )
    ]
    assert logged[0][0] == IMPROVEMENT_PLAN_FAILED_TITLE
