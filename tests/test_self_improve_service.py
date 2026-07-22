from types import SimpleNamespace

from app.tools.self_improve_service import SelfImproveService
from app.tools.self_update_service import SelfUpdateService


class _PlanClient:
    def complete(self, messages) -> str:
        content = messages[-1]["content"]
        if "File index" in content:
            return '{"files_to_read": ["app/main.py"]}'
        return (
            '{"changes": [{"path": "app/main.py", "content": "# updated\\n"}]}'
        )


def test_self_improve_service_applies_and_delegates_pr(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("original\n", encoding="utf-8")

    monkeypatch.setattr(
        "app.tools.self_improve_service.walk_app_files",
        lambda max_files=30: ["app/main.py"],
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
