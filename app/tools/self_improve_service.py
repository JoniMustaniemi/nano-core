from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from app.config import get_settings
from app.runtime.activity import activity
from app.runtime.dev import uvicorn_reload_enabled
from app.runtime.long_task_progress import LongTaskProgressReporter
from app.runtime.status_copy import (
    PLANNING_SELF_IMPROVE_TITLE,
    SELF_IMPROVE_WORKTREE_DETAIL,
    VERIFYING_SELF_IMPROVE_DETAIL,
    VERIFYING_SELF_IMPROVE_TITLE,
)
from app.tools.files import read_text_file, write_text_file
from app.tools.pr_service import PullRequestService
from app.tools.pr_verify import run_pr_lint, run_pr_verification
from app.tools.self_improve_planning import (
    SELECT_JSON_HINT,
    complete_json_dict,
    fallback_files_for_goal,
    file_selection_lines,
    parse_selection,
    plan_single_file_change,
)
from app.tools.self_improve_worktree import SelfImproveWorktree


@dataclass(frozen=True, slots=True)
class SelfImproveResult:
    ok: bool
    step: str
    changed_files: list[str] | None = None
    pr_url: str | None = None
    goal: str | None = None
    error: str | None = None
    reason: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def _fail_self_improve(
    *,
    step: str,
    error: str,
    goal: str,
    changed_files: list[str] | None = None,
    reason: str | None = None,
) -> SelfImproveResult:
    return SelfImproveResult(
        ok=False,
        step=step,
        error=error,
        goal=goal,
        changed_files=changed_files,
        reason=reason,
    )


def _plan_error_message(*, path: str, reason: str | None) -> tuple[str, str | None]:
    if reason == "old_text_not_found":
        return (
            f"The model could not match the exact text to replace in {path}.",
            reason,
        )
    if reason == "invalid_shape":
        return (
            f"The model returned an unusable change plan for {path}.",
            reason,
        )
    return (
        f"Could not parse change plan from the model for {path}.",
        reason or "invalid_json",
    )


def _validate_preferred_files(paths: list[str] | None, *, allowed: str) -> list[str]:
    if not paths:
        return []
    allowed_prefix = allowed.rstrip("/")
    validated: list[str] = []
    for raw_path in paths:
        path = str(raw_path).strip()
        if not path.startswith(allowed_prefix):
            continue
        try:
            read_text_file(path)
        except (OSError, ValueError):
            continue
        if path not in validated:
            validated.append(path)
    return validated


class SelfImproveService:
    """Orchestrated self-improvement: explore, plan, write, verify, PR."""

    def run(
        self,
        *,
        client: Any,
        goal: str,
        preferred_files: list[str] | None = None,
    ) -> SelfImproveResult:
        if uvicorn_reload_enabled():
            setup = SelfImproveWorktree.try_setup(goal=goal)
            if setup.error or setup.worktree is None:
                return _fail_self_improve(
                    step="preflight",
                    error=setup.error or "Could not create a self-improvement worktree.",
                    goal=goal,
                )
            activity.log(
                title=PLANNING_SELF_IMPROVE_TITLE,
                detail=SELF_IMPROVE_WORKTREE_DETAIL,
                source="tools.self_improve_service",
            )
            with setup.worktree.activate():
                return self._run_impl(
                    client=client,
                    goal=goal,
                    preferred_files=preferred_files,
                )

        return self._run_impl(
            client=client,
            goal=goal,
            preferred_files=preferred_files,
        )

    def _run_impl(
        self,
        *,
        client: Any,
        goal: str,
        preferred_files: list[str] | None,
    ) -> SelfImproveResult:
        settings = get_settings()
        allowed = settings.self_improve_allowed_prefix

        with LongTaskProgressReporter(task_name="self-improvement", goal=goal) as progress:
            progress.update(step="starting")
            activity.working(
                title=PLANNING_SELF_IMPROVE_TITLE,
                detail=goal,
                source="tools.self_improve_service",
            )

            files_to_read = _validate_preferred_files(preferred_files, allowed=allowed)
            progress.update(step="select")
            if not files_to_read:
                selection_lines = file_selection_lines(goal)
                select_messages = [
                    {
                        "role": "system",
                        "content": (
                            "Select files to edit for a self-improvement task. "
                            f"Only paths under {allowed} are allowed. "
                            f"Return JSON only: {SELECT_JSON_HINT} with at most "
                            f"{settings.self_improve_max_files} paths. No markdown fences."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Goal: {goal}\n\nKnown files:\n" + "\n".join(selection_lines)
                        ),
                    },
                ]
                selection = complete_json_dict(
                    client,
                    select_messages,
                    correction=(
                        "Your previous response was invalid. Return JSON only with key files_to_read. "
                        f"Example: {SELECT_JSON_HINT}"
                    ),
                )
                files_to_read = parse_selection(selection) if selection is not None else []
                if not files_to_read:
                    files_to_read = fallback_files_for_goal(goal, allowed=allowed)
                if selection is None and not files_to_read:
                    return _fail_self_improve(
                        step="select",
                        error="Could not parse file selection from the model.",
                        goal=goal,
                    )
            if not files_to_read:
                return _fail_self_improve(step="select", error="No files selected.", goal=goal)

            file_contents: dict[str, str] = {}
            for raw_path in files_to_read[: settings.self_improve_max_files]:
                path = str(raw_path)
                if not path.startswith(allowed.rstrip("/")):
                    continue
                try:
                    text = read_text_file(path)
                except (OSError, ValueError):
                    continue
                if len(text) > settings.self_improve_max_file_chars:
                    text = text[: settings.self_improve_max_file_chars]
                file_contents[path] = text

            if not file_contents:
                return _fail_self_improve(
                    step="read",
                    error="Could not read target files.",
                    goal=goal,
                )

            changed_files: list[str] = []
            file_paths = list(file_contents.keys())
            file_count = len(file_paths)
            progress.update(step="plan", file_count=file_count)
            for file_index, (path, content) in enumerate(file_contents.items(), start=1):
                progress.update(
                    step="plan",
                    current_file=path,
                    file_index=file_index,
                    file_count=file_count,
                    attempt=0,
                )

                def _on_attempt(
                    attempt: int,
                    *,
                    current_path: str = path,
                    current_file_index: int = file_index,
                ) -> None:
                    progress.update(
                        step="plan",
                        current_file=current_path,
                        file_index=current_file_index,
                        file_count=file_count,
                        attempt=attempt,
                    )

                planned = plan_single_file_change(
                    client,
                    goal=goal,
                    path=path,
                    content=content,
                    allowed=allowed,
                    on_attempt=_on_attempt,
                )
                if planned.parsed is None:
                    error, reason = _plan_error_message(path=path, reason=planned.reason)
                    return _fail_self_improve(
                        step="plan",
                        error=error,
                        goal=goal,
                        reason=reason,
                    )
                write_text_file(planned.parsed["path"], planned.parsed["content"])
                changed_files.append(planned.parsed["path"])

            if not changed_files:
                return _fail_self_improve(step="plan", error="No changes planned.", goal=goal)

            progress.update(step="lint")
            activity.working(
                title=VERIFYING_SELF_IMPROVE_TITLE,
                detail=VERIFYING_SELF_IMPROVE_DETAIL,
                source="tools.self_improve_service",
            )
            verify = run_pr_lint()
            if not verify.ok:
                return _fail_self_improve(
                    step="lint",
                    error=verify.error or "Lint checks failed.",
                    goal=goal,
                    changed_files=changed_files,
                )

            progress.update(step="verify")
            verify = run_pr_verification()
            if not verify.ok:
                return _fail_self_improve(
                    step="verify",
                    error=verify.error or "Verification failed.",
                    goal=goal,
                    changed_files=changed_files,
                )

            progress.update(step="pr")
            pr_result = PullRequestService().run(client=client)
            if not pr_result.ok:
                return _fail_self_improve(
                    step=pr_result.step,
                    error=pr_result.error or "Pull request failed.",
                    goal=goal,
                    changed_files=changed_files,
                )

            return SelfImproveResult(
                ok=True,
                step="complete",
                changed_files=changed_files,
                pr_url=pr_result.url,
                goal=goal,
            )
