from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from app.runtime.activity import activity
from app.tools.git_github import (
    collect_change_context,
    detect_default_base_branch,
    ensure_feature_branch,
    format_command_result,
    get_current_branch,
    gh_authenticated,
    gh_available,
    gh_missing_message,
    git_missing_message,
    has_publishable_changes,
    is_git_repo,
    qualify_head_branch,
    resolve_executable,
    run_git,
    run_gh,
    working_tree_dirty,
)
from app.tools.pr_naming import PrNamingService
from app.tools.pr_verify import command_display, run_pr_verification


@dataclass(frozen=True, slots=True)
class PrResult:
    ok: bool
    step: str
    url: str | None = None
    branch: str | None = None
    title: str | None = None
    base: str | None = None
    verified_with: str | None = None
    error: str | None = None
    output: str | None = None

    def to_json(self) -> str:
        """
        Serialize the result to JSON.

        Returns:
            JSON string representation.
        """
        return json.dumps(asdict(self), ensure_ascii=False)


class PullRequestService:
    def __init__(
        self,
        *,
        naming_service: PrNamingService | None = None,
    ) -> None:
        """
        Initialize the pull request service.

        Args:
            naming_service: Optional naming service override for tests.
        """
        self.naming_service = naming_service or PrNamingService()

    def run(self, *, client: Any) -> PrResult:
        """
        Run the full pull request workflow.

        Args:
            client: LLM client used for naming.

        Returns:
            Structured pull request result.
        """
        activity.working(
            title="Nano is preparing a pull request.",
            detail="Running preflight checks.",
            source="tools.pr_service",
        )

        if not is_git_repo():
            if resolve_executable("git") is None:
                return self._fail("preflight", git_missing_message())
            return self._fail("preflight", "Workspace is not a git repository.")

        if not gh_available():
            return self._fail("preflight", gh_missing_message())

        if not gh_authenticated():
            return self._fail("preflight", "GitHub CLI is not authenticated. Run gh auth login.")

        if not has_publishable_changes():
            return self._fail("preflight", "Nothing to open a pull request for.")

        context = collect_change_context()
        activity.log(
            title="Nano collected change context.",
            detail=json.dumps(
                {
                    "changed_files": context.get("changed_files", []),
                    "dirty": context.get("dirty"),
                },
                ensure_ascii=False,
            ),
            source="tools.pr_service",
        )

        activity.working(
            title="Nano is verifying the project.",
            detail="Running tests before any git writes.",
            source="tools.pr_service",
        )
        verify = run_pr_verification()
        if not verify.ok:
            activity.error(
                title="Verification failed.",
                detail=verify.error or verify.output,
                source="tools.pr_service",
            )
            return PrResult(
                ok=False,
                step="verify",
                verified_with=command_display(verify.command) if verify.command else None,
                error=verify.error or "Verification failed.",
                output=verify.output,
            )

        activity.log(
            title="Verification passed.",
            detail=command_display(verify.command),
            source="tools.pr_service",
        )

        activity.working(
            title="Nano is naming the pull request.",
            detail="Using the local model to derive branch and title.",
            source="tools.pr_service",
        )
        try:
            naming = self.naming_service.generate(client=client, context=context)
        except RuntimeError as exc:
            activity.error(
                title="Pull request naming failed.",
                detail=str(exc),
                source="tools.pr_service",
            )
            return self._fail("naming", str(exc))

        current_branch = get_current_branch()
        base_branch = detect_default_base_branch()
        if current_branch == base_branch or current_branch != naming.branch:
            activity.working(
                title="Nano is creating a feature branch.",
                detail=naming.branch,
                source="tools.pr_service",
            )
            branch_result = ensure_feature_branch(naming.branch)
            if branch_result.returncode != 0:
                return self._fail("branch", format_command_result(branch_result))
            current_branch = get_current_branch()

        if current_branch != naming.branch:
            return self._fail(
                "branch",
                f"Expected to be on {naming.branch} but am on {current_branch}.",
            )

        if working_tree_dirty():
            activity.working(
                title="Nano is committing changes.",
                detail=naming.commit_message,
                source="tools.pr_service",
            )
            add_result = run_git("add", "-A")
            if add_result.returncode != 0:
                return self._fail("commit", format_command_result(add_result))

            commit_result = run_git("commit", "-m", naming.commit_message)
            if commit_result.returncode != 0:
                return self._fail("commit", format_command_result(commit_result))

        activity.working(
            title="Nano is pushing the branch.",
            detail=naming.branch,
            source="tools.pr_service",
        )
        push_result = run_git("push", "-u", "origin", "HEAD")
        if push_result.returncode != 0:
            return self._fail("push", format_command_result(push_result))

        current_branch = get_current_branch()
        if current_branch == base_branch:
            return self._fail(
                "pr_create",
                f"Cannot open a pull request while still on the base branch {base_branch}.",
            )

        activity.working(
            title="Nano is opening the pull request.",
            detail=f"{current_branch} -> {base_branch}",
            source="tools.pr_service",
        )
        pr_result = run_gh(
            "pr",
            "create",
            "--title",
            naming.title,
            "--body",
            naming.body,
            "--base",
            base_branch,
        )
        if pr_result.returncode != 0:
            pr_result = run_gh(
                "pr",
                "create",
                "--title",
                naming.title,
                "--body",
                naming.body,
                "--base",
                base_branch,
                "--head",
                qualify_head_branch(current_branch),
            )
        if pr_result.returncode != 0:
            return PrResult(
                ok=False,
                step="pr_create",
                branch=naming.branch,
                title=naming.title,
                base=base_branch,
                verified_with=command_display(verify.command),
                error=format_command_result(pr_result),
                output=pr_result.stdout.strip() or pr_result.stderr.strip(),
            )

        url = pr_result.stdout.strip()
        activity.standby(
            title="Pull request created.",
            detail=url,
            source="tools.pr_service",
        )
        return PrResult(
            ok=True,
            step="complete",
            url=url,
            branch=current_branch,
            title=naming.title,
            base=base_branch,
            verified_with=command_display(verify.command),
        )

    def _fail(self, step: str, error: str) -> PrResult:
        activity.error(
            title="Pull request workflow failed.",
            detail=error,
            source="tools.pr_service",
        )
        return PrResult(ok=False, step=step, error=error)
