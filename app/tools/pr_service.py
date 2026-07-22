from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from app.runtime.activity import activity
from app.runtime.status_copy import (
    COLLECTED_CHANGE_CONTEXT_TITLE,
    COMMITTING_CHANGES_TITLE,
    CREATING_FEATURE_BRANCH_TITLE,
    NAMING_PR_TITLE,
    OPENING_PR_TITLE,
    PR_CREATED_TITLE,
    PR_NAMING_FAILED_TITLE,
    PR_WORKFLOW_FAILED_TITLE,
    PREPARING_PR_TITLE,
    PUSHING_BRANCH_TITLE,
    VERIFICATION_FAILED_TITLE,
    VERIFICATION_PASSED_TITLE,
    VERIFYING_PROJECT_TITLE,
)
from app.tools.git_github import (
    collect_change_context,
    detect_default_base_branch,
    ensure_feature_branch,
    format_command_result,
    get_current_branch,
    get_open_pull_request,
    gh_authenticated,
    gh_available,
    gh_missing_message,
    git_missing_message,
    has_publishable_changes,
    is_git_repo,
    qualify_head_branch,
    resolve_executable,
    run_gh,
    run_git,
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
            title=PREPARING_PR_TITLE,
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

        open_pr = get_open_pull_request()
        if open_pr is not None:
            branch_suffix = f" on {open_pr.branch}" if open_pr.branch else ""
            return PrResult(
                ok=False,
                step="preflight",
                url=open_pr.url,
                branch=open_pr.branch or None,
                title=open_pr.title,
                error=(
                    f"Pull request #{open_pr.number} is already open{branch_suffix} "
                    f"and waiting for review ({open_pr.title}). "
                    "Merge or close it before opening another."
                ),
            )

        if not has_publishable_changes():
            return self._fail("preflight", "Nothing to open a pull request for.")

        context = collect_change_context()
        activity.log(
            title=COLLECTED_CHANGE_CONTEXT_TITLE,
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
            title=VERIFYING_PROJECT_TITLE,
            detail="Running tests before any git writes.",
            source="tools.pr_service",
        )
        verify = run_pr_verification()
        if not verify.ok:
            activity.error(
                title=VERIFICATION_FAILED_TITLE,
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
            title=VERIFICATION_PASSED_TITLE,
            detail=command_display(verify.command),
            source="tools.pr_service",
        )

        activity.working(
            title=NAMING_PR_TITLE,
            detail="Using the local model to derive branch and title.",
            source="tools.pr_service",
        )
        try:
            naming = self.naming_service.generate(client=client, context=context)
        except RuntimeError as exc:
            activity.error(
                title=PR_NAMING_FAILED_TITLE,
                detail=str(exc),
                source="tools.pr_service",
            )
            return self._fail("naming", str(exc))

        current_branch = get_current_branch()
        base_branch = detect_default_base_branch()
        if current_branch == base_branch or current_branch != naming.branch:
            activity.working(
                title=CREATING_FEATURE_BRANCH_TITLE,
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
                title=COMMITTING_CHANGES_TITLE,
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
            title=PUSHING_BRANCH_TITLE,
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
            title=OPENING_PR_TITLE,
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
            title=PR_CREATED_TITLE,
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
            title=PR_WORKFLOW_FAILED_TITLE,
            detail=error,
            source="tools.pr_service",
        )
        return PrResult(ok=False, step=step, error=error)
