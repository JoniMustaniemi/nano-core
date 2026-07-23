from types import SimpleNamespace

from app.tools.self_improve_service import SelfImproveService, _fallback_files_for_goal
from app.tools.self_update_service import SelfUpdateService


class _PatchPlanClient:
    def complete(self, messages) -> str:
        content = messages[-1]["content"]
        if "Known files:" in content:
            return '{"files_to_read": ["app/runtime/status_copy.py"]}'
        if "old_text" in messages[0]["content"]:
            return (
                '{"path": "app/runtime/status_copy.py", '
                '"old_text": "SETTING_TIMER_TITLE = \\"I\'m setting a timer.\\"", '
                '"new_text": "SETTING_TIMER_TITLE = \\"I\'m starting a timer.\\""}'
            )
        return '{"path": "app/runtime/status_copy.py", "content": "# updated\\n"}'


class _PlanClient:
    def complete(self, messages) -> str:
        content = messages[-1]["content"]
        if "Known files:" in content:
            return '{"files_to_read": ["app/main.py"]}'
        return '{"path": "app/main.py", "content": "# updated\\n"}'


class _RetryPlanClient:
    def __init__(self) -> None:
        self.plan_attempts = 0

    def complete(self, messages) -> str:
        content = messages[-1]["content"]
        if "Known files:" in content:
            return '{"files_to_read": ["app/main.py"]}'
        if "Your previous response was invalid" in content:
            return '{"path": "app/main.py", "content": "# updated\\n"}'
        self.plan_attempts += 1
        return "not json"


def test_self_improve_service_rejects_invalid_selection_json(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("original\n", encoding="utf-8")
    monkeypatch.setattr(
        "app.tools.self_improve_service._file_selection_lines",
        lambda goal, limit=40: ["- app/main.py: Main entrypoint."],
    )
    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: SimpleNamespace(
            self_improve_allowed_prefix="app/",
            self_improve_max_files=5,
            self_improve_max_file_chars=8000,
        ),
    )

    class _BadSelectClient:
        def complete(self, messages) -> str:
            return "not json"

    result = SelfImproveService().run(client=_BadSelectClient(), goal="update main")

    assert not result.ok
    assert result.step == "select"
    assert "parse file selection" in (result.error or "").lower()


def test_self_improve_service_applies_and_delegates_pr(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("original\n", encoding="utf-8")

    monkeypatch.setattr(
        "app.tools.self_improve_service._file_selection_lines",
        lambda goal, limit=40: ["- app/main.py: Main entrypoint."],
    )
    monkeypatch.setattr(
        "app.tools.self_improve_service.run_pr_lint",
        lambda: SimpleNamespace(ok=True, error=None),
    )
    monkeypatch.setattr(
        "app.tools.self_improve_service.run_pr_verification",
        lambda: SimpleNamespace(ok=True, error=None),
    )
    monkeypatch.setattr(
        "app.tools.self_improve_service.PullRequestService.run",
        lambda self, client: SimpleNamespace(ok=True, url="https://example/pr", step="complete"),
    )
    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: SimpleNamespace(
            self_improve_allowed_prefix="app/",
            self_improve_max_files=5,
            self_improve_max_file_chars=8000,
        ),
    )

    result = SelfImproveService().run(client=_PlanClient(), goal="update main")
    assert result.ok
    assert result.changed_files == ["app/main.py"]


def test_self_improve_service_retries_invalid_plan_json(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("original\n", encoding="utf-8")
    monkeypatch.setattr(
        "app.tools.self_improve_service._file_selection_lines",
        lambda goal, limit=40: ["- app/main.py: Main entrypoint."],
    )
    monkeypatch.setattr(
        "app.tools.self_improve_service.run_pr_lint",
        lambda: SimpleNamespace(ok=True, error=None),
    )
    monkeypatch.setattr(
        "app.tools.self_improve_service.run_pr_verification",
        lambda: SimpleNamespace(ok=True, error=None),
    )
    monkeypatch.setattr(
        "app.tools.self_improve_service.PullRequestService.run",
        lambda self, client: SimpleNamespace(ok=True, url="https://example/pr", step="complete"),
    )
    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: SimpleNamespace(
            self_improve_allowed_prefix="app/",
            self_improve_max_files=5,
            self_improve_max_file_chars=8000,
        ),
    )

    client = _RetryPlanClient()
    result = SelfImproveService().run(client=client, goal="update main")

    assert result.ok
    assert client.plan_attempts == 1
    assert result.changed_files == ["app/main.py"]


def test_fallback_files_for_timer_message_goal() -> None:
    files = _fallback_files_for_goal(
        "making timer messages clearer",
        allowed="app/",
    )
    assert "app/runtime/status_copy.py" in files
    assert "app/assistant/flows/timer.py" in files


def test_self_improve_service_applies_patch_plan(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app" / "runtime").mkdir(parents=True)
    status_copy = (
        'SETTING_TIMER_TITLE = "I\'m setting a timer."\n'
        "SETTING_TIMER_DETAIL = \"Scheduling the requested timer.\"\n"
    )
    (tmp_path / "app" / "runtime" / "status_copy.py").write_text(status_copy, encoding="utf-8")

    monkeypatch.setattr(
        "app.tools.self_improve_service._file_selection_lines",
        lambda goal, limit=40: ["- app/runtime/status_copy.py: Status strings."],
    )
    monkeypatch.setattr(
        "app.tools.self_improve_service.run_pr_lint",
        lambda: SimpleNamespace(ok=True, error=None),
    )
    monkeypatch.setattr(
        "app.tools.self_improve_service.run_pr_verification",
        lambda: SimpleNamespace(ok=True, error=None),
    )
    monkeypatch.setattr(
        "app.tools.self_improve_service.PullRequestService.run",
        lambda self, client: SimpleNamespace(ok=True, url="https://example/pr", step="complete"),
    )
    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: SimpleNamespace(
            self_improve_allowed_prefix="app/",
            self_improve_max_files=5,
            self_improve_max_file_chars=8000,
        ),
    )

    result = SelfImproveService().run(
        client=_PatchPlanClient(),
        goal="making timer messages clearer",
    )

    assert result.ok
    assert result.changed_files == ["app/runtime/status_copy.py"]
    updated = (tmp_path / "app" / "runtime" / "status_copy.py").read_text(encoding="utf-8")
    assert 'SETTING_TIMER_TITLE = "I\'m starting a timer."' in updated


def test_self_improve_service_uses_goal_fallback_when_selection_invalid(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app" / "runtime").mkdir(parents=True)
    (tmp_path / "app" / "runtime" / "status_copy.py").write_text(
        'SETTING_TIMER_TITLE = "I\'m setting a timer."\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "app.tools.self_improve_service._file_selection_lines",
        lambda goal, limit=40: ["- app/runtime/status_copy.py: Status strings."],
    )
    monkeypatch.setattr(
        "app.tools.self_improve_service.run_pr_lint",
        lambda: SimpleNamespace(ok=True, error=None),
    )
    monkeypatch.setattr(
        "app.tools.self_improve_service.run_pr_verification",
        lambda: SimpleNamespace(ok=True, error=None),
    )
    monkeypatch.setattr(
        "app.tools.self_improve_service.PullRequestService.run",
        lambda self, client: SimpleNamespace(ok=True, url="https://example/pr", step="complete"),
    )
    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: SimpleNamespace(
            self_improve_allowed_prefix="app/",
            self_improve_max_files=5,
            self_improve_max_file_chars=8000,
        ),
    )

    class _BadSelectPatchClient:
        def complete(self, messages) -> str:
            if "Known files:" in messages[-1]["content"]:
                return "not json"
            return (
                '{"path": "app/runtime/status_copy.py", '
                '"old_text": "SETTING_TIMER_TITLE = \\"I\'m setting a timer.\\"", '
                '"new_text": "SETTING_TIMER_TITLE = \\"I\'m starting a timer.\\""}'
            )

    result = SelfImproveService().run(
        client=_BadSelectPatchClient(),
        goal="making timer messages clearer",
    )

    assert result.ok
    assert result.changed_files == ["app/runtime/status_copy.py"]


def test_self_update_rejects_dirty_tree(monkeypatch) -> None:
    monkeypatch.setattr("app.tools.self_update_service.is_git_repo", lambda: True)
    monkeypatch.setattr("app.tools.self_update_service.working_tree_dirty", lambda: True)
    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: SimpleNamespace(
            self_update_base_branch="",
            github_default_base_branch="main",
        ),
    )
    result = SelfUpdateService().run()
    assert not result.ok
    assert result.step == "preflight"


def test_self_update_switches_to_main_before_pull(monkeypatch) -> None:
    checkout_calls: list[str] = []

    def fake_checkout(name: str):
        checkout_calls.append(name)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def fake_run_git(*args):
        if args[:2] == ("fetch", "origin"):
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args[:3] == ("pull", "origin", "main"):
            return SimpleNamespace(returncode=0, stdout="Already up to date.", stderr="")
        if args[:4] == ("diff", "--name-only", "HEAD@{1}", "HEAD"):
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("app.tools.self_update_service.is_git_repo", lambda: True)
    monkeypatch.setattr("app.tools.self_update_service.working_tree_dirty", lambda: False)
    monkeypatch.setattr(
        "app.tools.self_update_service.get_current_branch",
        lambda: "feature/pr_naming",
    )
    monkeypatch.setattr("app.tools.self_update_service.checkout_branch", fake_checkout)
    monkeypatch.setattr("app.tools.self_update_service.run_git", fake_run_git)
    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: SimpleNamespace(
            self_update_base_branch="",
            github_default_base_branch="main",
        ),
    )

    result = SelfUpdateService().run()

    assert result.ok
    assert checkout_calls == ["main"]


def test_self_improve_service_uses_worktree_when_reload_enabled(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("NANO_UVICORN_RELOAD", "1")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("original\n", encoding="utf-8")

    worktree_path = tmp_path / "worktree"
    worktree_path.mkdir()
    (worktree_path / "app").mkdir()
    (worktree_path / "app" / "main.py").write_text("original\n", encoding="utf-8")

    from contextlib import contextmanager

    from app.tools.self_improve_worktree import SelfImproveWorktree, WorktreeSetup

    class _FakeWorktree(SelfImproveWorktree):
        def __init__(self) -> None:
            super().__init__(path=worktree_path, branch="nano/self-improve-test")

        @contextmanager
        def activate(self):
            from app.tools.workspace_context import workspace_override

            with workspace_override(worktree_path):
                yield worktree_path

    setup_calls: list[str] = []

    def fake_try_setup(*, goal: str) -> WorktreeSetup:
        setup_calls.append(goal)
        return WorktreeSetup(worktree=_FakeWorktree())

    monkeypatch.setattr(
        "app.tools.self_improve_service.SelfImproveWorktree.try_setup",
        fake_try_setup,
    )
    monkeypatch.setattr(
        "app.tools.self_improve_service._file_selection_lines",
        lambda goal, limit=40: ["- app/main.py: Main entrypoint."],
    )
    monkeypatch.setattr(
        "app.tools.self_improve_service.run_pr_lint",
        lambda: SimpleNamespace(ok=True, error=None),
    )
    monkeypatch.setattr(
        "app.tools.self_improve_service.run_pr_verification",
        lambda: SimpleNamespace(ok=True, error=None),
    )
    monkeypatch.setattr(
        "app.tools.self_improve_service.PullRequestService.run",
        lambda self, client: SimpleNamespace(ok=True, url="https://example/pr", step="complete"),
    )
    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: SimpleNamespace(
            self_improve_allowed_prefix="app/",
            self_improve_max_files=5,
            self_improve_max_file_chars=8000,
        ),
    )

    result = SelfImproveService().run(client=_PlanClient(), goal="update main")

    assert setup_calls == ["update main"]
    assert result.ok
    assert result.changed_files == ["app/main.py"]
    assert (tmp_path / "app" / "main.py").read_text(encoding="utf-8") == "original\n"
    assert (worktree_path / "app" / "main.py").read_text(encoding="utf-8") == "# updated\n"


def test_self_improve_service_worktree_setup_failure(monkeypatch) -> None:
    monkeypatch.setenv("NANO_UVICORN_RELOAD", "1")
    monkeypatch.setattr(
        "app.tools.self_improve_service.SelfImproveWorktree.try_setup",
        lambda goal: __import__(
            "app.tools.self_improve_worktree", fromlist=["WorktreeSetup"]
        ).WorktreeSetup(worktree=None, error="Workspace is not a git repository."),
    )

    result = SelfImproveService().run(
        client=SimpleNamespace(),
        goal="clearer timer messages",
    )

    assert result.ok is False
    assert result.step == "preflight"
    assert result.error == "Workspace is not a git repository."
