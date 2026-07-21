import json

import pytest

from app.tools.pr_naming import (
    PrNamingService,
    is_valid_slug,
    looks_like_file_list_body,
    sanitize_slug,
)


class _NamingClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls = 0

    def complete(self, messages) -> str:
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return response


def test_sanitize_slug_normalizes_text() -> None:
    assert sanitize_slug("Fix-Timer Bug!!") == "fix_timer_bug"


def test_is_valid_slug() -> None:
    assert is_valid_slug("fix_timer_bug") is True
    assert is_valid_slug("ab") is False
    assert is_valid_slug("Bad-Name") is False


def test_looks_like_file_list_body_detects_diff_stat_dump() -> None:
    body = (
        "app/assistant/agent_router.py: 14 ++\n"
        "app/assistant/answer_executor.py: 108 +\n"
        "app/assistant/orchestrator.py: 15 +"
    )

    assert looks_like_file_list_body(body)


def test_looks_like_file_list_body_allows_prose_summary() -> None:
    body = (
        "Adds a unified agent router and response pipeline so Nano can route "
        "requests before falling back to the planner."
    )

    assert not looks_like_file_list_body(body)


def test_pr_naming_service_retries_file_list_body(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.tools.pr_naming.ensure_unique_branch_slug", lambda slug: slug)
    client = _NamingClient(
        [
            json.dumps(
                {
                    "slug": "agent_router",
                    "title": "agent_router",
                    "commit_message": "agent_router",
                    "body": "app/assistant/agent_router.py: 14 ++\napp/assistant/orchestrator.py: 15 +",
                }
            ),
            json.dumps(
                {
                    "slug": "agent_router",
                    "title": "agent_router",
                    "commit_message": "agent_router",
                    "body": "Adds unified routing and response pipeline handling before planner fallback.",
                }
            ),
        ]
    )
    service = PrNamingService()

    naming = service.generate(
        client=client,
        context={
            "changed_files": ["app/assistant/agent_router.py"],
            "diff_stat": "2 files changed",
            "diff_patch": "diff",
            "unpushed_commits": [],
        },
    )

    assert naming.slug == "agent_router"
    assert "agent_router.py" not in naming.body
    assert client.calls == 2


def test_pr_naming_service_generates_valid_naming(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.tools.pr_naming.ensure_unique_branch_slug", lambda slug: slug)
    client = _NamingClient(
        [
            json.dumps(
                {
                    "slug": "fix_timer_cancel_bug",
                    "title": "fix_timer_cancel_bug",
                    "commit_message": "fix_timer_cancel_bug",
                    "body": "Fixes timer cancellation handling.",
                }
            )
        ]
    )
    service = PrNamingService()

    naming = service.generate(
        client=client,
        context={
            "changed_files": ["app/tools/timer_tools.py"],
            "diff_stat": "1 file changed",
            "diff_patch": "diff",
            "unpushed_commits": [],
        },
    )

    assert naming.slug == "fix_timer_cancel_bug"
    assert naming.branch == "feature/fix_timer_cancel_bug"
    assert naming.title == "fix_timer_cancel_bug"


def test_pr_naming_service_retries_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.tools.pr_naming.ensure_unique_branch_slug", lambda slug: slug)
    client = _NamingClient(
        [
            "not json",
            json.dumps(
                {
                    "slug": "add_github_pr",
                    "title": "add_github_pr",
                    "commit_message": "add_github_pr",
                    "body": "Adds GitHub pull request support.",
                }
            ),
        ]
    )
    service = PrNamingService()

    naming = service.generate(client=client, context={"changed_files": [], "diff_stat": "", "diff_patch": ""})

    assert naming.slug == "add_github_pr"
    assert client.calls == 2
