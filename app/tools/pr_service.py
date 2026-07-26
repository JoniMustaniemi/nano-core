from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from threading import Event
from typing import Any

from app.config import get_settings
from app.runtime.activity import activity
from app.runtime.status_copy import (
    COLLECTED_CHANGE_CONTEXT_TITLE,
    COMMITTING_CHANGES_TITLE,
    CREATING_FEATURE_BRANCH_TITLE,
    LINT_AUTO_FIXED_TITLE,
    LINT_CHECKS_FAILED_TITLE,
    LINT_CHECKS_PASSED_TITLE,
    NAMING_PR_DETAIL,
    NAMING_PR_TITLE,
    OPENING_PR_TITLE,
    PR_CREATED_TITLE,
    PR_LINT_TIMER_LABEL,
    PR_LINT_TIMER_SECONDS,
    PR_NAMING_FAILED_TITLE,
    PR_NAMING_TIMER_LABEL,
    PR_NAMING_TIMER_SECONDS,
    PR_OPENING_TIMER_LABEL,
    PR_OPENING_TIMER_SECONDS,
    PR_VERIFY_TIMER_LABEL,
    PR_WORKFLOW_CANCELLED_TITLE,
    PR_WORKFLOW_FAILED_TITLE,
    PREPARING_PR_LINT_DETAIL,
    PREPARING_PR_PREFLIGHT_DETAIL,
    PREPARING_PR_TITLE,
    PREPARING_PR_VERIFY_DETAIL,
    PUSHING_BRANCH_TITLE,
    VERIFICATION_FAILED_TITLE,
    VERIFICATION_PASSED_TITLE,
    VERIFYING_PROJECT_TITLE,
    lint_failure_detail,
    lint_failure_voice_message,
    running_tool_title,
)
from app.tools.git_command import (
    format_command_result,
    gh_missing_message,
    git_missing_message,
    resolve_executable,
    run_gh,
    run_git,
)
from app.tools.git_ops import (
    collect_change_context,
    ensure_feature_branch,
    get_current_branch,
    has_publishable_changes,
    is_git_repo,
    working_tree_dirty,
)
from app.tools.github_ops import (
    detect_default_base_branch,
    get_open_pull_request,
    gh_authenticated,
    gh_available,
    qualify_head_branch,
)
from app.tools.plan_implementation_runtime import is_cancelled
from app.tools.pr_naming import PrNamingService
from app.tools.pr_verify import command_display, run_pr_lint, run_pr_verification


def _finalize_pr_activity(result: PrResult) -> None:
    activity.clear_task_timer()
    if result.ok:
        return
    if result.step == "cancelled":
        activity.standby(
            title=PR_WORKFLOW_CANCELLED_TITLE,
            detail=result.error or "Pull request workflow was cancelled.",
            source="tools.pr_service",
        )
        return
    activity.standby(
        title=PR_WORKFLOW_FAILED_TITLE,
        detail=result.error or "I could not complete the pull request.",
        source="tools.pr_service",
    )


def _cancelled_pr_result() -> PrResult:
    return PrResult(ok=False, step="cancelled", error="Pull request workflow was cancelled.")


def _finalize_cancelled_pr() -> PrResult:
    result = _cancelled_pr_result()
    _finalize_pr_activity(result)
    return result


def _check_cancelled(cancel_event: Event | None) -> PrResult | None:
    if is_cancelled(cancel_event=cancel_event):
        return _finalize_cancelled_pr()
    return None


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

    def run(
        self,
        *,
        client: Any,
        announce: bool = True,
        cancel_event: Event | None = None,
    ) -> PrResult:
        """
        Run the full pull request workflow.

        Args:
            client: LLM client used for naming.
            announce: When True, emit a spoken intent before starting the workflow.
            cancel_event: Optional cancellation signal for plan implementation.

        Returns:
            Structured pull request result.
        """
        cancelled = _check_cancelled(cancel_event)
        if cancelled is not None:
            return cancelled

        activity.working(
            title=PREPARING_PR_TITLE,
            detail=PREPARING_PR_PREFLIGHT_DETAIL,
            source="tools.pr_service",
        )
        if announce:
            activity.announce_voice(running_tool_title("create_pull_request"))

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
            result = PrResult(
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
            _finalize_pr_activity(result)
            return result

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
            detail=PREPARING_PR_LINT_DETAIL,
            source="tools.pr_service",
        )
        cancelled = _check_cancelled(cancel_event)
        if cancelled is not None:
            return cancelled
        activity.start_task_timer(PR_LINT_TIMER_LABEL, PR_LINT_TIMER_SECONDS)
        lint = run_pr_lint()
        if not lint.ok:
            failure_detail = lint_failure_detail(
                lint.error or "Lint checks failed.",
                lint.output,
            )
            activity.error(
                title=LINT_CHECKS_FAILED_TITLE,
                detail=failure_detail,
                source="tools.pr_service",
            )
            activity.log(
                title="Lint check output",
                detail=failure_detail,
                source="tools.pr_service.lint",
            )
            activity.announce_voice(lint_failure_voice_message(lint.error or "Lint checks failed."))
            result = PrResult(
                ok=False,
                step="lint",
                verified_with=command_display(lint.command) if lint.command else None,
                error=lint.error or "Lint checks failed.",
                output=lint.output,
            )
            _finalize_pr_activity(result)
            return result

        if lint.command:
            if getattr(lint, "auto_fixed", False):
                activity.log(
                    title=LINT_AUTO_FIXED_TITLE,
                    detail=command_display([*lint.command, "--fix"]),
                    source="tools.pr_service",
                )
            activity.log(
                title=LINT_CHECKS_PASSED_TITLE,
                detail=command_display(lint.command),
                source="tools.pr_service",
            )

        activity.working(
            title=VERIFYING_PROJECT_TITLE,
            detail=PREPARING_PR_VERIFY_DETAIL,
            source="tools.pr_service",
        )
        activity.log(
            title=VERIFYING_PROJECT_TITLE,
            detail="Running the full test suite. This can take a few minutes.",
            source="tools.pr_service",
        )
        cancelled = _check_cancelled(cancel_event)
        if cancelled is not None:
            return cancelled
        settings = get_settings()
        activity.start_task_timer(
            PR_VERIFY_TIMER_LABEL,
            settings.github_pr_verify_timeout_seconds,
        )
        verify = run_pr_verification()
        if not verify.ok:
            failure_detail = verify.output or verify.error or "Verification failed."
            activity.error(
                title=VERIFICATION_FAILED_TITLE,
                detail=failure_detail,
                source="tools.pr_service",
            )
            result = PrResult(
                ok=False,
                step="verify",
                verified_with=command_display(verify.command) if verify.command else None,
                error=verify.error or "Verification failed.",
                output=verify.output,
            )
            _finalize_pr_activity(result)
            return result

        activity.log(
            title=VERIFICATION_PASSED_TITLE,
            detail=command_display(verify.command),
            source="tools.pr_service",
        )

        cancelled = _check_cancelled(cancel_event)
        if cancelled is not None:
            return cancelled

        activity.working(
            title=NAMING_PR_TITLE,
            detail=NAMING_PR_DETAIL,
            source="tools.pr_service",
        )
        activity.start_task_timer(PR_NAMING_TIMER_LABEL, PR_NAMING_TIMER_SECONDS)
        try:
            naming = self.naming_service.generate(client=client, context=context)
        except RuntimeError as exc:
            activity.error(
                title=PR_NAMING_FAILED_TITLE,
                detail=str(exc),
                source="tools.pr_service",
            )
            return self._fail("naming", str(exc))

        cancelled = _check_cancelled(cancel_event)
        if cancelled is not None:
            return cancelled

        current_branch = get_current_branch()
        base_branch = detect_default_base_branch()
        if current_branch == base_branch or current_branch != naming.branch:
            cancelled = _check_cancelled(cancel_event)
            if cancelled is not None:
                return cancelled
            activity.working(
                title=CREATING_FEATURE_BRANCH_TITLE,
                detail=naming.branch,
                source="tools.pr_service",
            )
            branch_result = ensure_feature_branch(naming.branch)
            if branch_result.returncode != 0:
                return self._fail("branch", format_command_result(branch_result))
            cancelled = _check_cancelled(cancel_event)
            if cancelled is not None:
                return cancelled
            current_branch = get_current_branch()

        if current_branch != naming.branch:
            return self._fail(
                "branch",
                f"Expected to be on {naming.branch} but am on {current_branch}.",
            )

        if working_tree_dirty():
            cancelled = _check_cancelled(cancel_event)
            if cancelled is not None:
                return cancelled
            activity.working(
                title=COMMITTING_CHANGES_TITLE,
                detail=naming.commit_message,
                source="tools.pr_service",
            )
            add_result = run_git("add", "-A")
            if add_result.returncode != 0:
                return self._fail("commit", format_command_result(add_result))
            cancelled = _check_cancelled(cancel_event)
            if cancelled is not None:
                return cancelled

            commit_result = run_git("commit", "-m", naming.commit_message)
            if commit_result.returncode != 0:
                return self._fail("commit", format_command_result(commit_result))
            cancelled = _check_cancelled(cancel_event)
            if cancelled is not None:
                return cancelled

        cancelled = _check_cancelled(cancel_event)
        if cancelled is not None:
            return cancelled
        activity.working(
            title=PUSHING_BRANCH_TITLE,
            detail=naming.branch,
            source="tools.pr_service",
        )
        push_result = run_git("push", "-u", "origin", "HEAD")
        if push_result.returncode != 0:
            return self._fail("push", format_command_result(push_result))
        cancelled = _check_cancelled(cancel_event)
        if cancelled is not None:
            return cancelled

        current_branch = get_current_branch()
        if current_branch == base_branch:
            return self._fail(
                "pr_create",
                f"Cannot open a pull request while still on the base branch {base_branch}.",
            )

        cancelled = _check_cancelled(cancel_event)
        if cancelled is not None:
            return cancelled
        activity.working(
            title=OPENING_PR_TITLE,
            detail=f"{current_branch} -> {base_branch}",
            source="tools.pr_service",
        )
        activity.start_task_timer(PR_OPENING_TIMER_LABEL, PR_OPENING_TIMER_SECONDS)
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
        cancelled = _check_cancelled(cancel_event)
        if cancelled is not None:
            return cancelled
        if pr_result.returncode != 0:
            cancelled = _check_cancelled(cancel_event)
            if cancelled is not None:
                return cancelled
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
            cancelled = _check_cancelled(cancel_event)
            if cancelled is not None:
                return cancelled
        if pr_result.returncode != 0:
            stdout = pr_result.stdout.strip()
            stderr = pr_result.stderr.strip()
            result = PrResult(
                ok=False,
                step="pr_create",
                branch=naming.branch,
                title=naming.title,
                base=base_branch,
                verified_with=command_display(verify.command),
                error=format_command_result(pr_result),
                output=stdout or stderr,
            )
            _finalize_pr_activity(result)
            return result

        url = pr_result.stdout.strip()
        if not url:
            return self._fail("pr_create", "GitHub CLI did not return a pull request URL.")
        activity.clear_task_timer()
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
        result = PrResult(ok=False, step=step, error=error)
        _finalize_pr_activity(result)
        return result
