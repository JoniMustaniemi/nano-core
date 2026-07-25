from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.assistant.rules.parsing import looks_like_truncated_json
from app.config import get_settings
from app.llm.factory import get_code_llm_client, get_llm_client
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
from app.tools.improvement_plan_service import PLAN_TEMPERATURE, _validate_preferred_files
from app.tools.pr_service import PrResult, PullRequestService
from app.tools.self_improve_planning import (
    complete_json_dict_with_raw,
    looks_like_llm_unavailable,
)

APPLY_REPLACEMENT_HINT = (
    '{"files": [{"path": "app/...", "replacements": [{"find": "...", "replace": "..."}]}]}'
)
APPLY_FULL_FILE_HINT = '{"files": [{"path": "app/...", "content": "..."}]}'
IMPLEMENTATION_SOURCE = "tools.improvement_plan_implementation"
_NO_DIFF_ERROR = "Planned changes produced no file diff."
_RAW_PREVIEW_MAX_CHARS = 200
_RETRY_RAW_PREVIEW_MAX_CHARS = 500
_SMALL_FILE_LINE_THRESHOLD = 200
_FULL_FILE_FALLBACK_AFTER_FAILURES = 2


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
        return ImplementationPreflightResult(
            ok=False, error="Improvement plan not found.", status_code=404
        )
    if plan.status not in allowed_statuses:
        return ImplementationPreflightResult(
            ok=False,
            error="Plan is not available for implementation.",
            status_code=409,
        )

    settings = get_settings()
    files = _validate_preferred_files(
        _files_from_plan(plan), allowed=settings.self_improve_allowed_prefix
    )
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


def _parse_replacement_items(raw: object) -> list[tuple[str, str]]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("Response must include a non-empty replacements array.")
    parsed: list[tuple[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        find = item.get("find")
        replace = item.get("replace")
        if isinstance(find, str) and isinstance(replace, str):
            parsed.append((find, replace))
    if not parsed:
        raise ValueError("No valid replacements were returned.")
    return parsed


def _apply_replacements(content: str, replacements: list[tuple[str, str]]) -> str:
    result = content
    for find, replace in replacements:
        count = result.count(find)
        if count != 1:
            raise ValueError(
                f"Replacement find text must appear exactly once (found {count} times)."
            )
        result = result.replace(find, replace, 1)
    return result


def _parse_apply_payload(
    payload: dict[str, Any],
    *,
    allowed_files: list[str],
    file_contents: dict[str, str],
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
        if not normalized:
            continue
        canonical = allowed_map.get(normalized)
        if canonical is None:
            raise ValueError(f"Unexpected file path: {normalized}")
        if canonical in seen:
            continue

        content = item.get("content")
        replacements = item.get("replacements")
        if isinstance(content, str):
            seen.add(canonical)
            parsed.append((canonical, content))
            continue
        if replacements is not None:
            original = file_contents.get(canonical, "")
            replacement_pairs = _parse_replacement_items(replacements)
            seen.add(canonical)
            parsed.append((canonical, _apply_replacements(original, replacement_pairs)))

    if not parsed:
        raise ValueError("No valid file edits were returned.")
    return parsed


def _prefer_full_file_apply(file_contents: dict[str, str]) -> bool:
    if len(file_contents) != 1:
        return False
    content = next(iter(file_contents.values()))
    return len(content.splitlines()) <= _SMALL_FILE_LINE_THRESHOLD


def _build_apply_correction(
    *,
    full_file_only: bool,
    truncated: bool = False,
) -> str:
    if full_file_only:
        base = (
            "Your previous response was invalid. Return JSON only with key files. "
            f"Required shape: {APPLY_FULL_FILE_HINT}. "
            "Return the complete updated file content for each path. "
            "Do not use replacements or markdown fences."
        )
    else:
        base = (
            "Your previous response was invalid. Return JSON only with key files. "
            f"Preferred example: {APPLY_REPLACEMENT_HINT}"
        )
    if truncated:
        return f"Your JSON was cut off. Return one complete JSON object. {base}"
    return base


def _retry_assistant_content(last_raw: str) -> str:
    if len(last_raw) <= _RETRY_RAW_PREVIEW_MAX_CHARS:
        return last_raw
    preview = _truncate_raw_preview(last_raw, max_chars=_RETRY_RAW_PREVIEW_MAX_CHARS)
    return f"{preview}\n...[response truncated for context]"


def _build_apply_messages(
    *,
    goal: str,
    body: str,
    file_contents: dict[str, str],
    allowed_files: list[str],
    prefer_full_file: bool = False,
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
    if prefer_full_file:
        system_content = (
            "You implement a focused improvement plan for Nano, a local AI assistant codebase. "
            "Return JSON only with full updated file contents. "
            f"Required shape: {APPLY_FULL_FILE_HINT}. "
            f"You must return exactly these paths: {required_paths}. "
            "Include every listed target file exactly once. "
            "Do not use replacements, markdown fences, or commentary."
        )
    else:
        system_content = (
            "You implement a focused improvement plan for Nano, a local AI assistant codebase. "
            "Return JSON only with minimal search/replace edits. "
            f"Preferred shape: {APPLY_REPLACEMENT_HINT}. "
            "Each replacement find string must match the current file exactly once. "
            f"You must return exactly these paths: {required_paths}. "
            "Include every listed target file exactly once. "
            f"Alternatively you may return full file contents using: {APPLY_FULL_FILE_HINT}. "
            "Do not add markdown fences or commentary."
        )
    return [
        {
            "role": "system",
            "content": system_content,
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
            return ImplementationResult(
                ok=False, step="load", plan_id=plan_id, error="Plan not found."
            )

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
        activity.announce_voice(IMPLEMENTING_IMPROVEMENT_PLAN_TITLE)

        with LongTaskProgressReporter(task_name="self improvement", goal=plan.goal) as reporter:
            reporter.update(
                step="plan", current_file=allowed_files[0], file_count=len(allowed_files)
            )

            apply_result = self._apply_plan(
                plan,
                allowed_files=allowed_files,
                reporter=reporter,
            )
            if not apply_result.ok:
                improvement_plans.restore_pending(plan_id)
                failure_message = _format_apply_failure_message(apply_result.error)
                activity.standby(
                    title=IMPROVEMENT_PLAN_IMPLEMENTATION_FAILED_TITLE,
                    detail=failure_message,
                    source=IMPLEMENTATION_SOURCE,
                )
                activity.announce_voice(failure_message)
                return apply_result

            reporter.update(step="lint")
            pr_result = self.pr_service.run(
                client=get_code_llm_client(),
                announce=True,
            )
            if not pr_result.ok:
                _restore_plan_files(allowed_files)
                improvement_plans.restore_pending(plan_id)
                failure_message = _format_implementation_pr_failure(pr_result)
                activity.standby(
                    title=IMPROVEMENT_PLAN_IMPLEMENTATION_FAILED_TITLE,
                    detail=failure_message,
                    source=IMPLEMENTATION_SOURCE,
                )
                activity.announce_voice(failure_message)
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
        activity.announce_voice(IMPROVEMENT_PLAN_IMPLEMENTED_TITLE)
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
        reporter: LongTaskProgressReporter | None = None,
    ) -> ImplementationResult:
        plan_id = plan.id
        settings = get_settings()
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

        messages = _build_apply_messages(
            goal=plan.goal,
            body=plan.body,
            file_contents=file_contents,
            allowed_files=allowed_files,
            prefer_full_file=_prefer_full_file_apply(file_contents),
        )
        full_file_only = _prefer_full_file_apply(file_contents)
        max_tokens = settings.self_improve_plan_max_tokens
        max_attempts = settings.self_improve_apply_max_attempts
        payload: dict[str, Any] | None = None
        edits: list[tuple[str, str]] = []
        apply_error: str | None = None
        last_parse_error: str | None = None
        last_raw = ""
        total_attempts = 0

        for client in (get_code_llm_client(), get_llm_client()):
            if apply_error is not None:
                break
            conversation = list(messages)
            json_failures = 0
            for _attempt in range(max_attempts):
                total_attempts += 1
                if reporter is not None:
                    reporter.update(attempt=total_attempts)

                apply_correction = _build_apply_correction(full_file_only=full_file_only)
                payload, last_raw = complete_json_dict_with_raw(
                    client,
                    conversation,
                    correction=apply_correction,
                    attempts=1,
                    max_tokens=max_tokens,
                    temperature=PLAN_TEMPERATURE,
                )
                if payload is None:
                    if looks_like_llm_unavailable(last_raw):
                        apply_error = last_raw
                        break
                    json_failures += 1
                    if json_failures >= _FULL_FILE_FALLBACK_AFTER_FAILURES:
                        full_file_only = True
                    truncated = looks_like_truncated_json(last_raw)
                    retry_correction = _build_apply_correction(
                        full_file_only=full_file_only,
                        truncated=truncated,
                    )
                    conversation.extend(
                        [
                            {"role": "assistant", "content": _retry_assistant_content(last_raw)},
                            {"role": "user", "content": retry_correction},
                        ]
                    )
                    continue

                try:
                    edits = _parse_apply_payload(
                        payload,
                        allowed_files=allowed_files,
                        file_contents=file_contents,
                    )
                    break
                except ValueError as exc:
                    last_parse_error = str(exc)
                    json_failures += 1
                    if json_failures >= _FULL_FILE_FALLBACK_AFTER_FAILURES:
                        full_file_only = True
                    parse_correction = _build_apply_correction(
                        full_file_only=full_file_only,
                    )
                    parse_correction = (
                        f"Your JSON structure was invalid: {exc}. Fix the JSON. {parse_correction}"
                    )
                    conversation.extend(
                        [
                            {"role": "assistant", "content": _retry_assistant_content(last_raw)},
                            {"role": "user", "content": parse_correction},
                        ]
                    )
                    payload = None
                    continue

            if payload is not None and edits:
                break

        if payload is None or not edits:
            if apply_error:
                error = apply_error
            elif last_parse_error is not None:
                error = last_parse_error
            elif total_attempts > 0:
                error = _format_invalid_json_error(total_attempts, last_raw)
            else:
                error = "Could not apply planned code changes."
            return ImplementationResult(
                ok=False,
                step="apply",
                plan_id=plan_id,
                error=error,
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


def _truncate_raw_preview(raw: str, max_chars: int = _RAW_PREVIEW_MAX_CHARS) -> str:
    cleaned = " ".join(raw.split())
    if len(cleaned) > max_chars:
        return cleaned[:max_chars] + "..."
    return cleaned


def _format_invalid_json_error(attempts: int, last_raw: str) -> str:
    if looks_like_truncated_json(last_raw):
        message = (
            f"Model returned truncated JSON after {attempts} attempts. "
            "Try a larger code model or re-draft the plan."
        )
    else:
        message = f"Model returned invalid JSON after {attempts} attempts."
    preview = _truncate_raw_preview(last_raw)
    if preview:
        message = f"{message} Last response preview: {preview}"
    return message


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
