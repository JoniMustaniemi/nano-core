from pathlib import Path
from types import SimpleNamespace

from app.tools.self_improve_worktree import SelfImproveWorktree, _unique_self_improve_branch


def test_unique_self_improve_branch_adds_suffix_when_branch_exists(monkeypatch) -> None:
    existing = {"nano/self-improve-clearer_timer_messages"}

    monkeypatch.setattr(
        "app.tools.self_improve_worktree.branch_exists",
        lambda name: name in existing,
    )

    branch = _unique_self_improve_branch("clearer timer messages")

    assert branch == "nano/self-improve-clearer_timer_messages_2"


def test_try_setup_fails_when_not_git_repo(monkeypatch) -> None:
    monkeypatch.setattr("app.tools.self_improve_worktree.is_git_repo", lambda: False)

    setup = SelfImproveWorktree.try_setup(goal="clearer timer messages")

    assert setup.worktree is None
    assert setup.error == "Workspace is not a git repository."


def test_try_setup_creates_worktree(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("app.tools.self_improve_worktree.is_git_repo", lambda: True)
    monkeypatch.setattr(
        "app.tools.self_improve_worktree.detect_default_base_branch",
        lambda: "main",
    )
    monkeypatch.setattr(
        "app.tools.self_improve_worktree.branch_exists",
        lambda name: False,
    )

    created_paths: list[str] = []

    def fake_run_git_main(*args: str):
        if args[:2] == ("worktree", "add"):
            path = Path(args[4])
            path.mkdir(parents=True, exist_ok=True)
            (path / "app").mkdir(exist_ok=True)
            created_paths.append(str(path))
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    removed_paths: list[str] = []

    def fake_remove_worktree(path: Path) -> None:
        removed_paths.append(str(path))

    monkeypatch.setattr("app.tools.self_improve_worktree._run_git_main", fake_run_git_main)
    monkeypatch.setattr("app.tools.self_improve_worktree._remove_worktree", fake_remove_worktree)

    setup = SelfImproveWorktree.try_setup(goal="clearer timer messages")
    assert setup.error is None
    assert setup.worktree is not None

    with setup.worktree.activate() as active_root:
        assert active_root == setup.worktree.path

    assert created_paths
    assert removed_paths == [str(setup.worktree.path)]
