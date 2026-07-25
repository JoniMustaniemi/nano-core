from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.config import get_settings
from app.llm.factory import get_code_llm_client
from app.memory import improvement_plans
from app.memory.models import ImprovementPlan
from app.runtime.activity import activity
from app.runtime.long_task_progress import LongTaskProgressReporter
from app.runtime.status_copy import (
    APPLYING_PLANNED_CHANGES_DETAIL,
    IMPLEMENTING_IMPROVEMENT_PLAN_TITLE,
    IMPROVEMENT_PLAN_IMPLEMENTATION_FAILED_TITLE,
    IMPROVEMENT_PLAN_IMPLEMENTED_DETAIL,
    IMPROVEMENT_PLAN_IMPLEMENTED_TITLE,
    running_tool_title,
)
from app.tools.files import read_text_file, write_text_file
from app.tools.git_command import run_git
from app.tools.git_github import (
    get_open_pull_request,
    gh_authenticated,
    gh_available,
    gh_missing_message,
    git_missing_message,
    is_git_repo,
    resolve_executable,
    working_tree_dirty,
)
from app.tools.improvement_plan_service import _validate_preferred_files
from app.tools.pr_service import PrResult, PullRequestService
from app.tools.self_improve_planning import complete_json_dict

APPLY_JSON_HINT = '{"files": [{"path": "app/...", "content": "..."}]}'
IMPLEMENTATION_SOURCE = "tools.improvement_plan_implementation"
IMPLEMENTATION_ANNOUNCE_SOURCE = "tools.improvement_plan_implementation.announce"
_NO_DIFF_ERROR = "Planned changes produced no file diff."


@dataclass(frozen=True, slots=True)
class ImplementationPreflightResult:
    ok: bool
    error: str | None = None
    status_code: int = 400


@dataclass(frozen=True, slots=True)
class ImplementationResult:
    ok: bool
    step: str
    plan_id: int | None = None
    pr_url: str | None = None
    error: str | None = None


def _files_from_plan(plan: ImprovementPlan) -> list[str]:
    try:
        files = json.loads(plan.files_json)
        if not isinstance(files, list):
            return []
    except json.JSONDecodeError:
        return []
    return [str(path) for path in files if str(path).strip()]


def _normalize_plan_path(raw_path: str) -> str:
    cleaned = str(raw_path).strip().replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned


def _normalize_allowed_files(allowed_files: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for path in allowed_files:
        normalized = _normalize_plan_path(path)
        if normalized:
            mapping[normalized] = path
    return mapping


def check_implementation_preflight(
    plan: ImprovementPlan | None,
    *,
    allowed_statuses: tuple[str, ...] = ("pending",),
) -> ImplementationPreflightResult:
    if plan is None:
        return ImplementationPreflightResult(ok=False, error="Improvement plan not found.", status_code=404)
    if plan.status not in allowed_statuses:
        return ImplementationPreflightResult(
            ok=False,
            error="Plan is not available for implementation.",
            status_code=409,
        )

    settings = get_settings()
    files = _validate_preferred_files(_files_from_plan(plan), allowed=settings.self_improve_allowed_prefix)
    if not files:
        return ImplementationPreflightResult(
            ok=False,
            error="Plan has no valid target files under the allowed prefix.",
        )

    if not is_git_repo():
        if resolve_executable("git") is None:
            return ImplementationPreflightResult(ok=False, error=git_missing_message())
        return ImplementationPreflightResult(ok=False, error="Workspace is not a git repository.")

    if not gh_available():
        return ImplementationPreflightResult(ok=False, error=gh_missing_message())

    if not gh_authenticated():
        return ImplementationPreflightResult(
            ok=False,
            error="GitHub CLI is not authenticated. Run gh auth login.",
        )

    if working_tree_dirty():
        return ImplementationPreflightResult(
            ok=False,
            error="Working tree has uncommitted changes. Commit or stash them first.",
        )

    open_pr = get_open_pull_request()
    if open_pr is not None:
        return ImplementationPreflightResult(
            ok=False,
            error=(
                f"Pull request #{open_pr.number} is already open and waiting for review "
                f"({open_pr.title}). Merge or close it before implementing another plan."
            ),
        )

    return ImplementationPreflightResult(ok=True)


def _parse_apply_payload(
    payload: dict[str, Any],
    *,
    allowed_files: list[str],
) -> list[tuple[str, str]]:
    raw_files = payload.get("files", [])
    if not isinstance(raw_files, list) or not raw_files:
        raise ValueError("Response must include a non-empty files array.")

    allowed_map = _normalize_allowed_files(allowed_files)
    parsed: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in raw_files:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_plan_path(str(item.get("path", "")))
        content = item.get("content")
        if not normalized or not isinstance(content, str):
            continue
        canonical = allowed_map.get(normalized)
        if canonical is None:
            raise ValueError(f"Unexpected file path: {normalized}")
        if canonical in seen:
            continue
        seen.add(canonical)
        parsed.append((canonical, content))

    if not parsed:
        raise ValueError("No valid file edits were returned.")
    return parsed


def _build_apply_messages(
    *,
    goal: str,
    body: str,
    file_contents: dict[str, str],
    allowed_files: list[str],
) -> list[dict[str, str]]:
    sections = [
        f"Goal: {goal}",
        "",
        "Improvement plan:",
        body,
        "",
        "Current file contents:",
    ]
    for path, content in file_contents.items():
        sections.extend([f"### {path}", content, ""])
    required_paths = ", ".join(allowed_files)
    return [
        {
            "role": "system",
            "content": (
                "You implement a focused improvement plan for Nano, a local AI assistant codebase. "
                "Return JSON only with the full updated file contents. "
                f"Use this shape: {APPLY_JSON_HINT}. "
                f"You must return exactly these paths: {required_paths}. "
                "Include every listed target file exactly once. "
                "Do not add markdown fences or commentary."
            ),
        },
        {
            "role": "user",
            "content": "\n".join(sections),
        },
    ]


def _restore_plan_files(paths: list[str]) -> None:
    for path in paths:
        run_git("restore", "--", path)


class ImprovementPlanImplementationService:
    """Apply a drafted improvement plan and open a pull request."""

    def __init__(
        self,
        *,
        pr_service: PullRequestService | None = None,
    ) -> None:
        self.pr_service = pr_service or PullRequestService()

    def run(self, plan_id: int) -> ImplementationResult:
        plan = improvement_plans.get_plan(plan_id)
        if plan is None:
            return ImplementationResult(ok=False, step="load", plan_id=plan_id, error="Plan not found.")

        preflight = check_implementation_preflight(plan, allowed_statuses=("implementing",))
        if not preflight.ok:
            return ImplementationResult(
                ok=False,
                step="preflight",
                plan_id=plan_id,
                error=preflight.error,
            )

        settings = get_settings()
        allowed_files = _validate_preferred_files(
            _files_from_plan(plan),
            allowed=settings.self_improve_allowed_prefix,
        )
        if not allowed_files:
            return ImplementationResult(
                ok=False,
                step="preflight",
                plan_id=plan_id,
                error="Plan has no valid target files.",
            )

        activity.working(
            title=IMPLEMENTING_IMPROVEMENT_PLAN_TITLE,
            detail=APPLYING_PLANNED_CHANGES_DETAIL,
            source=IMPLEMENTATION_SOURCE,
        )
        _emit_voice_announcement(IMPLEMENTING_IMPROVEMENT_PLAN_TITLE)

        with LongTaskProgressReporter(task_name="self improvement", goal=plan.goal) as reporter:
            reporter.update(step="plan", current_file=allowed_files[0], file_count=len(allowed_files))

            apply_result = self._apply_plan(plan, allowed_files=allowed_files)
            if not apply_result.ok:
                improvement_plans.restore_pending(plan_id)
                failure_message = _format_apply_failure_message(apply_result.error)
                activity.standby(
                    title=IMPROVEMENT_PLAN_IMPLEMENTATION_FAILED_TITLE,
                    detail=failure_message,
                    source=IMPLEMENTATION_SOURCE,
                )
                _emit_voice_announcement(failure_message)
                return apply_result

            reporter.update(step="lint")
            _emit_voice_announcement(running_tool_title("create_pull_request"))
            pr_result = self.pr_service.run(client=get_code_llm_client())
            if not pr_result.ok:
                _restore_plan_files(allowed_files)
                improvement_plans.restore_pending(plan_id)
                failure_message = _format_implementation_pr_failure(pr_result)
                activity.standby(
                    title=IMPROVEMENT_PLAN_IMPLEMENTATION_FAILED_TITLE,
                    detail=failure_message,
                    source=IMPLEMENTATION_SOURCE,
                )
                _emit_voice_announcement(failure_message)
                return ImplementationResult(
                    ok=False,
                    step=pr_result.step,
                    plan_id=plan_id,
                    error=pr_result.error or "Pull request workflow failed.",
                )

        improvement_plans.delete_plan(plan_id)
        activity.standby(
            title=IMPROVEMENT_PLAN_IMPLEMENTED_TITLE,
            detail=IMPROVEMENT_PLAN_IMPLEMENTED_DETAIL,
            source=IMPLEMENTATION_SOURCE,
        )
        _emit_voice_announcement(IMPROVEMENT_PLAN_IMPLEMENTED_TITLE)
        return ImplementationResult(
            ok=True,
            step="complete",
            plan_id=plan_id,
            pr_url=pr_result.url,
        )

    def _apply_plan(
        self,
        plan: ImprovementPlan,
        *,
        allowed_files: list[str],
    ) -> ImplementationResult:
        plan_id = plan.id
        file_contents: dict[str, str] = {}
        for path in allowed_files:
            try:
                file_contents[path] = read_text_file(path)
            except (OSError, ValueError) as exc:
                return ImplementationResult(
                    ok=False,
                    step="read",
                    plan_id=plan_id,
                    error=str(exc),
                )

        client = get_code_llm_client()
        messages = _build_apply_messages(
            goal=plan.goal,
            body=plan.body,
            file_contents=file_contents,
            allowed_files=allowed_files,
        )
        payload = complete_json_dict(
            client,
            messages,
            correction=(
                "Your previous response was invalid. Return JSON only with key files. "
                f"Example: {APPLY_JSON_HINT}"
            ),
        )
        if payload is None:
            return ImplementationResult(
                ok=False,
                step="apply",
                plan_id=plan_id,
                error="Could not apply planned code changes.",
            )

        try:
            edits = _parse_apply_payload(payload, allowed_files=allowed_files)
        except ValueError as exc:
            return ImplementationResult(
                ok=False,
                step="apply",
                plan_id=plan_id,
                error=str(exc),
            )

        changed_edits: list[tuple[str, str]] = []
        for path, content in edits:
            if file_contents.get(path) == content:
                continue
            changed_edits.append((path, content))

        if not changed_edits:
            return ImplementationResult(
                ok=False,
                step="apply",
                plan_id=plan_id,
                error=_NO_DIFF_ERROR,
            )

        for path, content in changed_edits:
            try:
                write_text_file(path, content)
            except (OSError, ValueError) as exc:
                return ImplementationResult(
                    ok=False,
                    step="write",
                    plan_id=plan_id,
                    error=str(exc),
                )

        return ImplementationResult(ok=True, step="apply", plan_id=plan_id)


def _format_implementation_pr_failure(result: PrResult) -> str:
    step = str(result.step or "").strip()
    error = str(result.error or "").strip()
    if step == "lint":
        return "Lint checks failed, so I declined to commit anything or open a pull request."
    if step == "verify":
        return "Your tests failed, so I declined to commit anything or open a pull request."
    if step == "preflight" and "nothing" in error.lower():
        return "There is nothing to publish, so I did not open a pull request."
    if step == "preflight" and "already open" in error.lower():
        title = str(result.title or "").strip()
        if title:
            return (
                f"An open pull request is already waiting for your review ({title}). "
                "Resolve it on GitHub before I open another."
            )
        return (
            "An open pull request is already waiting for your review. "
            "Resolve it on GitHub before I open another."
        )
    if error:
        return f"I could not implement the improvement plan: {error}"
    return IMPROVEMENT_PLAN_IMPLEMENTATION_FAILED_TITLE


def _format_apply_failure_message(error: str | None) -> str:
    cleaned = (error or "").strip()
    if cleaned:
        return f"{IMPROVEMENT_PLAN_IMPLEMENTATION_FAILED_TITLE} {cleaned}"
    return IMPROVEMENT_PLAN_IMPLEMENTATION_FAILED_TITLE


def _pr_failure_detail(result: PrResult) -> str:
    return _format_implementation_pr_failure(result)


def _emit_voice_announcement(message: str) -> None:
    spoken = message.strip().rstrip(".")
    if not spoken:
        return
    activity.log(
        title=spoken,
        detail=spoken,
        source=IMPLEMENTATION_ANNOUNCE_SOURCE,
    )
