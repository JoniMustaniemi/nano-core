import json

import pytest

from app.tools.pr_naming import (
    PrNamingService,
    humanize_slug,
    is_valid_slug,
    looks_like_file_list_body,
    looks_like_llm_unavailable,
    sanitize_pr_title,
    sanitize_slug,
    slug_looks_generic,
    title_looks_low_effort,
)


class _NamingClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls = 0

    def complete(self, messages) -> str:
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return response


def test_slug_looks_generic_rejects_start_nano_patterns() -> None:
    context = {
        "current_branch": "feature/start_nano_2_2_2",
        "recent_commits": "f689441 start_nano_2_2_2",
        "unpushed_commits": ["504802b start_nano_2_2_2_0724"],
    }

    assert slug_looks_generic("start_nano", context)
    assert slug_looks_generic("start_nano_2_2_2", context)
    assert slug_looks_generic("start_nano_2_2_2_0724", context)
    assert not slug_looks_generic("identity_request_ack", context)


def test_pr_naming_service_retries_generic_slug(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.tools.pr_naming.ensure_unique_branch_slug", lambda slug: slug)
    client = _NamingClient(
        [
            json.dumps(
                {
                    "slug": "start_nano_2_2_2",
                    "title": "Start nano iteration",
                    "commit_message": "start_nano_2_2_2",
                    "body": "Another start nano branch.",
                }
            ),
            json.dumps(
                {
                    "slug": "identity_request_ack",
                    "title": "Acknowledge identity questions before answering",
                    "commit_message": "identity_request_ack",
                    "body": "Adds immediate acknowledgement for identity requests.",
                }
            ),
        ]
    )
    service = PrNamingService()

    naming = service.generate(
        client=client,
        context={
            "changed_files": ["app/web/static/home-chat.js", "app/assistant/rules/intents.py"],
            "diff_stat": "2 files changed",
            "diff_patch": "diff",
            "unpushed_commits": ["504802b start_nano_2_2_2_0724"],
            "recent_commits": "f689441 start_nano_2_2_2",
            "current_branch": "feature/start_nano_2_2_2",
        },
    )

    assert naming.slug == "identity_request_ack"
    assert client.calls == 2


def test_pr_naming_service_falls_back_to_meaningful_slug_for_generic_llm_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.tools.pr_naming.ensure_unique_branch_slug", lambda slug: slug)
    client = _NamingClient(
        [
            json.dumps(
                {
                    "slug": "start_nano",
                    "title": "Start nano",
                    "commit_message": "start_nano",
                    "body": "Generic placeholder.",
                }
            ),
            json.dumps(
                {
                    "slug": "start_nano_2",
                    "title": "Start nano again",
                    "commit_message": "start_nano_2",
                    "body": "Still generic.",
                }
            ),
        ]
    )
    service = PrNamingService()

    naming = service.generate(
        client=client,
        context={
            "changed_files": ["app/web/static/home-chat.js", "app/assistant/rules/intents.py"],
            "diff_stat": "2 files changed",
            "diff_patch": "diff",
            "unpushed_commits": [],
            "recent_commits": "",
            "current_branch": "main",
        },
    )

    assert naming.slug == "home_chat_rules_intents"
    assert naming.slug != "start_nano"
    assert client.calls == 2


def test_title_looks_low_effort_detects_slug_copy() -> None:
    assert title_looks_low_effort("fix_timer_cancel_bug", "fix_timer_cancel_bug") is True
    assert (
        title_looks_low_effort("Fix timer cancellation handling", "fix_timer_cancel_bug") is False
    )


def test_sanitize_pr_title_trims_and_caps_length() -> None:
    long_title = "Improve pull request naming by reading diffs and generating human titles"
    assert len(sanitize_pr_title(long_title)) <= 72


def test_humanize_slug() -> None:
    assert humanize_slug("fix_timer_bug") == "Fix timer bug"


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


def test_looks_like_llm_unavailable_detects_setup_message() -> None:
    assert looks_like_llm_unavailable(
        "Local LLM is not available yet. Set LLM_MODEL_PATH to a GGUF model file."
    )


def test_pr_naming_service_falls_back_when_llm_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.tools.pr_naming.ensure_unique_branch_slug", lambda slug: slug)
    client = _NamingClient(
        [
            "Local LLM is not available yet. Set LLM_MODEL_PATH to a GGUF model file.",
        ]
    )
    service = PrNamingService()

    naming = service.generate(
        client=client,
        context={
            "changed_files": ["app/web/home.py", "app/web/static/home.js"],
            "diff_stat": "2 files changed",
            "diff_patch": "diff",
            "unpushed_commits": [],
        },
    )

    assert naming.slug == "web_home"
    assert naming.branch == "feature/web_home"
    assert naming.title == "Update home and home"
    assert client.calls == 1


def test_pr_naming_service_retries_file_list_body(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.tools.pr_naming.ensure_unique_branch_slug", lambda slug: slug)
    client = _NamingClient(
        [
            json.dumps(
                {
                    "slug": "agent_router",
                    "title": "Add unified agent routing before planner fallback",
                    "commit_message": "agent_router",
                    "body": "app/assistant/agent_router.py: 14 ++\napp/assistant/orchestrator.py: 15 +",
                }
            ),
            json.dumps(
                {
                    "slug": "agent_router",
                    "title": "Add unified agent routing before planner fallback",
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
    assert naming.title == "Add unified agent routing before planner fallback"
    assert "agent_router.py" not in naming.body
    assert client.calls == 2


def test_pr_naming_service_generates_valid_naming(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.tools.pr_naming.ensure_unique_branch_slug", lambda slug: slug)
    client = _NamingClient(
        [
            json.dumps(
                {
                    "slug": "fix_timer_cancel_bug",
                    "title": "Fix timer cancellation handling",
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
    assert naming.title == "Fix timer cancellation handling"


def test_pr_naming_service_retries_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.tools.pr_naming.ensure_unique_branch_slug", lambda slug: slug)
    client = _NamingClient(
        [
            "not json",
            json.dumps(
                {
                    "slug": "add_github_pr",
                    "title": "Add GitHub pull request workflow",
                    "commit_message": "add_github_pr",
                    "body": "Adds GitHub pull request support.",
                }
            ),
        ]
    )
    service = PrNamingService()

    naming = service.generate(
        client=client, context={"changed_files": [], "diff_stat": "", "diff_patch": ""}
    )

    assert naming.slug == "add_github_pr"
    assert naming.title == "Add GitHub pull request workflow"
    assert client.calls == 2


class _NoneResponseClient:
    def complete(self, messages) -> None:
        return None


def test_pr_naming_service_falls_back_when_client_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.tools.pr_naming.ensure_unique_branch_slug", lambda slug: slug)
    service = PrNamingService()

    naming = service.generate(
        client=_NoneResponseClient(),
        context={"changed_files": ["app/main.py"], "diff_stat": "", "diff_patch": ""},
    )

    assert naming.slug == "code_update"
    assert naming.branch == "feature/code_update"
    assert naming.title == "Update main"
