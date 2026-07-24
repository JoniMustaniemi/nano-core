from types import SimpleNamespace

import pytest

from app.tools.git_command import _normalize_output, resolve_executable, run_gh
from app.tools.git_github import (
    OpenPullRequest,
    ensure_feature_branch,
    ensure_unique_branch_slug,
    get_open_pull_request,
)


def test_ensure_feature_branch_checks_out_existing_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run_git(*args: str):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("app.tools.git_ops.branch_exists", lambda name: True)
    monkeypatch.setattr("app.tools.git_ops.run_git", fake_run_git)

    result = ensure_feature_branch("feature/add_github_pr")

    assert result.returncode == 0
    assert calls == [("checkout", "feature/add_github_pr")]


def test_ensure_feature_branch_creates_missing_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run_git(*args: str):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("app.tools.git_ops.branch_exists", lambda name: False)
    monkeypatch.setattr("app.tools.git_ops.run_git", fake_run_git)

    result = ensure_feature_branch("feature/add_github_pr")

    assert result.returncode == 0
    assert calls == [("checkout", "-b", "feature/add_github_pr")]


def test_resolve_executable_finds_git_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.tools.git_command.get_settings",
        lambda: type("Settings", (), {"git_executable": "", "github_cli_path": ""})(),
    )
    monkeypatch.setattr("app.tools.git_command.shutil.which", lambda name: None)
    monkeypatch.setattr("app.tools.git_command.os.name", "nt")
    monkeypatch.setattr(
        "app.tools.git_command.Path.exists",
        lambda self: str(self).endswith("Git\\cmd\\git.exe"),
    )

    resolved = resolve_executable("git")

    assert resolved is not None
    assert resolved.endswith("git.exe")


def test_run_gh_returns_clear_error_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.tools.git_command.resolve_executable", lambda name: None)

    result = run_gh("--version")

    assert result.returncode == 127
    assert "GitHub CLI" in result.stderr


def test_normalize_output_treats_none_as_empty() -> None:
    assert _normalize_output(None) == ""
    assert _normalize_output("hello\n") == "hello\n"


def test_run_git_handles_none_subprocess_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.tools.git_command.resolve_executable", lambda name: "git")

    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout=None, stderr=None)

    monkeypatch.setattr("app.tools.git_command.subprocess.run", fake_run)

    from app.tools.git_command import run_git

    result = run_git("status")

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_ensure_unique_branch_slug_returns_base_when_free(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.tools.git_ops.branch_exists", lambda name: False)

    assert ensure_unique_branch_slug("proactive_outreach") == "proactive_outreach"


def test_ensure_unique_branch_slug_uses_date_suffix_before_numeric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.tools.git_ops.branch_exists",
        lambda name: name == "feature/start_nano",
    )

    slug = ensure_unique_branch_slug("start_nano")

    assert slug.startswith("start_nano_")
    assert slug != "start_nano_2"
    assert len(slug) <= 48


def test_ensure_unique_branch_slug_uses_random_suffix_when_dated_branch_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.tools.git_ops.datetime",
        type(
            "FixedDateTime",
            (),
            {
                "now": staticmethod(
                    lambda tz=None: __import__("datetime").datetime(
                        2026, 7, 24, tzinfo=__import__("datetime").UTC
                    )
                )
            },
        ),
    )
    monkeypatch.setattr(
        "app.tools.git_ops.secrets.token_hex",
        lambda nbytes: "a1b2",
    )

    def branch_exists(name: str) -> bool:
        return name in {"feature/start_nano", "feature/start_nano_0724"}

    monkeypatch.setattr("app.tools.git_ops.branch_exists", branch_exists)

    assert ensure_unique_branch_slug("start_nano") == "start_nano_a1b2"


def test_get_open_pull_request_returns_none_when_no_open_prs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.tools.github_ops.run_gh",
        lambda *args: SimpleNamespace(returncode=0, stdout="[]", stderr=""),
    )

    assert get_open_pull_request() is None


def test_get_open_pull_request_parses_first_open_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = (
        '[{"number": 7, "url": "https://github.com/org/repo/pull/7", '
        '"title": "fix timer", "headRefName": "feature/fix_timer"}]'
    )
    monkeypatch.setattr(
        "app.tools.github_ops.run_gh",
        lambda *args: SimpleNamespace(returncode=0, stdout=payload, stderr=""),
    )

    open_pr = get_open_pull_request()

    assert open_pr == OpenPullRequest(
        number=7,
        url="https://github.com/org/repo/pull/7",
        title="fix timer",
        branch="feature/fix_timer",
    )
