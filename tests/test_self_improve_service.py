from types import SimpleNamespace

from app.tools.self_improve_planning import fallback_files_for_goal, plan_max_tokens
from app.tools.self_improve_service import SelfImproveService


def _self_improve_settings(**overrides):
    defaults = {
        "self_improve_allowed_prefix": "app/",
        "self_improve_max_files": 5,
        "self_improve_max_file_chars": 8000,
        "llm_max_tokens": 512,
        "self_improve_plan_max_tokens": 8192,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _large_file_padding(lines: int = 201) -> str:
    return "".join(f"# padding {index}\n" for index in range(lines))


class _PatchPlanClient:
    def complete(self, messages, **kwargs) -> str:
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
    def complete(self, messages, **kwargs) -> str:
        content = messages[-1]["content"]
        if "Known files:" in content:
            return '{"files_to_read": ["app/main.py"]}'
        return '{"path": "app/main.py", "content": "# updated\\n"}'


class _RetryPlanClient:
    def __init__(self) -> None:
        self.plan_attempts = 0

    def complete(self, messages, **kwargs) -> str:
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
        "app.tools.self_improve_planning.file_selection_lines",
        lambda goal, limit=40: ["- app/main.py: Main entrypoint."],
    )
    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: _self_improve_settings(),
    )

    class _BadSelectClient:
        def complete(self, messages, **kwargs) -> str:
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
        "app.tools.self_improve_planning.file_selection_lines",
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
        lambda: _self_improve_settings(),
    )

    result = SelfImproveService().run(client=_PlanClient(), goal="update main")
    assert result.ok
    assert result.changed_files == ["app/main.py"]


def test_self_improve_service_retries_invalid_plan_json(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("original\n", encoding="utf-8")
    monkeypatch.setattr(
        "app.tools.self_improve_planning.file_selection_lines",
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
        lambda: _self_improve_settings(),
    )

    client = _RetryPlanClient()
    result = SelfImproveService().run(client=client, goal="update main")

    assert result.ok
    assert client.plan_attempts == 1
    assert result.changed_files == ["app/main.py"]


def test_fallback_files_for_timer_message_goal() -> None:
    files = fallback_files_for_goal(
        "making timer messages clearer",
        allowed="app/",
    )
    assert "app/runtime/status_copy.py" in files
    assert "app/assistant/flows/timer.py" in files
    assert "app/assistant/rules/messages.py" in files


def test_self_improve_service_applies_patch_plan(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app" / "runtime").mkdir(parents=True)
    status_copy = (
        _large_file_padding()
        + 'SETTING_TIMER_TITLE = "I\'m setting a timer."\n'
        + "SETTING_TIMER_DETAIL = \"Scheduling the requested timer.\"\n"
    )
    (tmp_path / "app" / "runtime" / "status_copy.py").write_text(status_copy, encoding="utf-8")

    monkeypatch.setattr(
        "app.tools.self_improve_planning.file_selection_lines",
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
        lambda: _self_improve_settings(),
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
        _large_file_padding()
        + 'SETTING_TIMER_TITLE = "I\'m setting a timer."\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "app.tools.self_improve_planning.file_selection_lines",
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
        lambda: _self_improve_settings(),
    )

    class _BadSelectPatchClient:
        def complete(self, messages, **kwargs) -> str:
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
        "app.tools.self_improve_planning.file_selection_lines",
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
        lambda: _self_improve_settings(),
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


def test_plan_max_tokens_scales_with_file_size() -> None:
    settings = _self_improve_settings()
    small = plan_max_tokens("x" * 100, settings=settings)
    large = plan_max_tokens("x" * 4200, settings=settings)
    assert small == 562
    assert large == 2612


def test_plan_uses_elevated_max_tokens_for_large_file(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app" / "assistant" / "rules").mkdir(parents=True)
    path = "app/assistant/rules/messages.py"
    content = "# header\n" + ("x = 1\n" * 700)
    (tmp_path / "app" / "assistant" / "rules" / "messages.py").write_text(content, encoding="utf-8")

    recorded: list[dict[str, int | float | None]] = []

    class _RecordingClient:
        def complete(self, messages, **kwargs):
            recorded.append(
                {
                    "max_tokens": kwargs.get("max_tokens"),
                    "temperature": kwargs.get("temperature"),
                }
            )
            user_content = messages[-1]["content"]
            if "Known files:" in user_content:
                return f'{{"files_to_read": ["{path}"]}}'
            if "old_text" in messages[0]["content"]:
                return (
                    f'{{"path": "{path}", '
                    '"old_text": "# header\\n", '
                    '"new_text": "# updated header\\n"}'
                )
            return f'{{"path": "{path}", "content": "# updated\\n"}}'

    monkeypatch.setattr(
        "app.tools.self_improve_planning.file_selection_lines",
        lambda goal, limit=40: [f"- {path}: Message helpers."],
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
    monkeypatch.setattr("app.config.get_settings", lambda: _self_improve_settings())

    result = SelfImproveService().run(
        client=_RecordingClient(),
        goal="improve message helpers",
    )

    assert result.ok
    planning_calls = [call for call in recorded if call["temperature"] == 0.1]
    assert planning_calls
    assert any(call["max_tokens"] is not None and call["max_tokens"] > 512 for call in planning_calls)


def test_patch_retry_gets_old_text_not_found_hint(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text(_large_file_padding() + "original value\n", encoding="utf-8")
    corrections: list[str] = []

    class _PatchRetryClient:
        def complete(self, messages, **kwargs):
            user_content = messages[-1]["content"]
            if "Known files:" in user_content:
                return '{"files_to_read": ["app/main.py"]}'
            if "old_text was not found verbatim" in user_content:
                corrections.append(user_content)
                return (
                    '{"path": "app/main.py", '
                    '"old_text": "original value\\n", '
                    '"new_text": "updated value\\n"}'
                )
            return (
                '{"path": "app/main.py", '
                '"old_text": "wrong snippet", '
                '"new_text": "updated value\\n"}'
            )

    monkeypatch.setattr(
        "app.tools.self_improve_planning.file_selection_lines",
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
    monkeypatch.setattr("app.config.get_settings", lambda: _self_improve_settings())

    result = SelfImproveService().run(client=_PatchRetryClient(), goal="update main")

    assert result.ok
    assert corrections
    assert any("old_text was not found verbatim" in correction for correction in corrections)


def test_full_file_plan_succeeds_for_messages_sized_content(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app" / "assistant" / "rules").mkdir(parents=True)
    path = "app/assistant/rules/messages.py"
    original = "# header\n" + ("value = 1\n" * 700)
    (tmp_path / "app" / "assistant" / "rules" / "messages.py").write_text(original, encoding="utf-8")
    updated = "# updated header\n" + ("value = 1\n" * 700)

    class _TokenAwareClient:
        def __init__(self) -> None:
            self.patch_attempts = 0

        def complete(self, messages, **kwargs):
            user_content = messages[-1]["content"]
            if "Known files:" in user_content:
                return f'{{"files_to_read": ["{path}"]}}'
            if "old_text" in messages[0]["content"]:
                self.patch_attempts += 1
                return "not json"
            max_tokens = kwargs.get("max_tokens")
            if max_tokens is not None and max_tokens <= 512:
                return '{"path": "' + path + '", "content": "' + updated[:200]
            import json

            return json.dumps({"path": path, "content": updated})

    monkeypatch.setattr(
        "app.tools.self_improve_planning.file_selection_lines",
        lambda goal, limit=40: [f"- {path}: Message helpers."],
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
    monkeypatch.setattr("app.config.get_settings", lambda: _self_improve_settings())

    client = _TokenAwareClient()
    result = SelfImproveService().run(client=client, goal="improve message helpers")

    assert result.ok
    assert client.patch_attempts == 3
    assert result.changed_files == [path]
    written = (tmp_path / "app" / "assistant" / "rules" / "messages.py").read_text(encoding="utf-8")
    assert written.startswith("# updated header")


def test_self_improve_service_uses_preferred_files_without_selection_llm(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app" / "assistant" / "rules").mkdir(parents=True)
    path = "app/assistant/rules/messages.py"
    (tmp_path / "app" / "assistant" / "rules" / "messages.py").write_text(
        "# header\nvalue = 1\n",
        encoding="utf-8",
    )
    selection_calls: list[str] = []

    class _PreferredFileClient:
        def complete(self, messages, **kwargs) -> str:
            user_content = messages[-1]["content"]
            if "Known files:" in user_content:
                selection_calls.append(user_content)
            return f'{{"path": "{path}", "content": "# updated\\n"}}'

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
    monkeypatch.setattr("app.config.get_settings", lambda: _self_improve_settings())

    result = SelfImproveService().run(
        client=_PreferredFileClient(),
        goal="improve message helpers",
        preferred_files=[path],
    )

    assert result.ok
    assert selection_calls == []
    assert result.changed_files == [path]


def test_small_file_skips_patch_planning(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app" / "assistant" / "rules").mkdir(parents=True)
    path = "app/assistant/rules/messages.py"
    (tmp_path / "app" / "assistant" / "rules" / "messages.py").write_text(
        "# header\nvalue = 1\n",
        encoding="utf-8",
    )
    saw_patch_prompt = False

    class _SmallFileClient:
        def complete(self, messages, **kwargs) -> str:
            nonlocal saw_patch_prompt
            if "old_text" in messages[0]["content"]:
                saw_patch_prompt = True
            user_content = messages[-1]["content"]
            if "Known files:" in user_content:
                return f'{{"files_to_read": ["{path}"]}}'
            return f'{{"path": "{path}", "content": "# updated\\n"}}'

    monkeypatch.setattr(
        "app.tools.self_improve_planning.file_selection_lines",
        lambda goal, limit=40: [f"- {path}: Message helpers."],
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
    monkeypatch.setattr("app.config.get_settings", lambda: _self_improve_settings())

    result = SelfImproveService().run(client=_SmallFileClient(), goal="improve message helpers")

    assert result.ok
    assert not saw_patch_prompt


def test_self_improve_service_plan_failure_returns_reason(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app" / "assistant" / "rules").mkdir(parents=True)
    path = "app/assistant/rules/messages.py"
    (tmp_path / "app" / "assistant" / "rules" / "messages.py").write_text(
        "# header\nvalue = 1\n",
        encoding="utf-8",
    )

    class _BadPlanClient:
        def complete(self, messages, **kwargs) -> str:
            user_content = messages[-1]["content"]
            if "Known files:" in user_content:
                return f'{{"files_to_read": ["{path}"]}}'
            return "not json"

    monkeypatch.setattr(
        "app.tools.self_improve_planning.file_selection_lines",
        lambda goal, limit=40: [f"- {path}: Message helpers."],
    )
    monkeypatch.setattr("app.config.get_settings", lambda: _self_improve_settings())

    result = SelfImproveService().run(client=_BadPlanClient(), goal="improve message helpers")

    assert not result.ok
    assert result.step == "plan"
    assert result.reason == "invalid_json"
