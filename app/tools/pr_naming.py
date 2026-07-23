from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from app.assistant.rules.parsing import extract_json
from app.tools.git_github import ensure_unique_branch_slug

_SLUG_PATTERN = re.compile(r"^[a-z0-9_]{3,48}$")
_FILE_LINE_PATTERN = re.compile(
    r"^[\s\-•*]*(?:[\w./@-]+/)?[\w./@-]+\.[a-z0-9]+:\s*[\d\s+\-|]+$",
    re.IGNORECASE,
)
_LLM_UNAVAILABLE_MARKERS = (
    "Local LLM is not available yet",
    "LLM_MODEL_PATH",
)


@dataclass(frozen=True, slots=True)
class PrNaming:
    slug: str
    title: str
    commit_message: str
    body: str
    branch: str


def _complete_text(client: Any, messages: list[dict[str, str]]) -> str:
    raw = client.complete(messages=messages)
    if not isinstance(raw, str):
        return ""
    return raw.strip()


class PrNamingService:
    def generate(self, *, client: Any, context: dict[str, Any]) -> PrNaming:
        """
        Generate PR naming metadata from repository change context.

        Args:
            client: LLM client used to generate naming JSON.
            context: Change context from git_github.collect_change_context.

        Returns:
            Validated naming metadata.

        Raises:
            RuntimeError: If naming cannot be generated or validated.
        """
        prompt = _build_user_prompt(context)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        raw = ""
        naming: PrNaming | None = None

        for _attempt in range(2):
            raw = _complete_text(client, messages)
            if looks_like_llm_unavailable(raw):
                return _build_fallback_naming(context)
            naming = _parse_naming(raw, context=context)
            if naming is not None and not looks_like_file_list_body(naming.body):
                return naming
            messages.extend(
                [
                    {"role": "assistant", "content": raw},
                    {
                        "role": "user",
                        "content": _correction_message(
                            naming=naming,
                            invalid_json=naming is None,
                        ),
                    },
                ]
            )

        if naming is not None and not looks_like_llm_unavailable(raw):
            body = _generate_prose_body(client=client, context=context, slug=naming.slug)
            if body and not looks_like_file_list_body(body) and not looks_like_llm_unavailable(body):
                return _replace_body(naming, body)

        naming = _parse_naming(raw, context=context, use_fallback_body=True)
        if naming is not None and not looks_like_file_list_body(naming.body):
            return naming

        return _build_fallback_naming(context)


_SYSTEM_PROMPT = (
    "You name git branches and pull requests from code diffs. "
    "Return JSON only with keys slug, title, commit_message, body. "
    "slug and title must be lowercase snake_case using only a-z, 0-9, and underscores, "
    "3 to 48 characters. slug must describe the code change from the diff. "
    "commit_message subject must equal slug; an optional body line may follow after a blank line. "
    "body must be 1-3 sentences of normal prose explaining what changed and why a reviewer should care. "
    "Never put file paths, diff stats, line counts, bullet lists of files, or patch excerpts in body. "
    "Use the diff only as context to understand the change."
)

_BODY_SYSTEM_PROMPT = (
    "Write a pull request description for human reviewers. "
    "Return plain text only: 1-3 sentences explaining what the code change does and why. "
    "Do not list files, paths, diff stats, or line counts."
)


def looks_like_llm_unavailable(raw: str) -> bool:
    """
    Return whether model output indicates the local LLM is unavailable.

    Args:
        raw: Raw model response.

    Returns:
        True when the response is a known LLM setup error instead of naming JSON.
    """
    return any(marker in raw for marker in _LLM_UNAVAILABLE_MARKERS)


def looks_like_file_list_body(body: str) -> bool:
    """
    Return whether text looks like a copied diff stat or file inventory.

    Args:
        body: Candidate pull request body.

    Returns:
        True when the body appears to enumerate files instead of summarizing work.
    """
    lines = [line.strip() for line in body.strip().splitlines() if line.strip()]
    if not lines:
        return True

    file_like_lines = sum(1 for line in lines if _FILE_LINE_PATTERN.match(line))
    if file_like_lines >= 2:
        return True
    if len(lines) >= 3 and file_like_lines / len(lines) >= 0.5:
        return True

    lowered = body.lower()
    if "file changed" in lowered or "files changed" in lowered:
        return True

    return False


def sanitize_slug(raw: str) -> str:
    """
    Normalize a raw slug into snake_case.

    Args:
        raw: Raw slug candidate.

    Returns:
        Sanitized slug.
    """
    lowered = raw.strip().lower().replace("-", "_").replace(" ", "_")
    cleaned = re.sub(r"[^a-z0-9_]+", "_", lowered)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned[:48]


def is_valid_slug(slug: str) -> bool:
    """
    Return whether a slug matches naming rules.

    Args:
        slug: Candidate slug.

    Returns:
        True when the slug is valid.
    """
    return bool(_SLUG_PATTERN.fullmatch(slug))


def _build_user_prompt(context: dict[str, Any]) -> str:
    changed_files = context.get("changed_files", [])
    files_text = "\n".join(f"- {path}" for path in changed_files) or "- (no changed files listed)"
    unpushed = context.get("unpushed_commits", [])
    unpushed_text = "\n".join(unpushed) or "(none)"
    return (
        "Name this change for a git feature branch and pull request.\n"
        "The pull request body must explain the change in prose, not repeat the file list below.\n\n"
        f"Changed files:\n{files_text}\n\n"
        f"Diff stat:\n{context.get('diff_stat', '') or '(empty)'}\n\n"
        f"Diff patch:\n{context.get('diff_patch', '') or '(empty)'}\n\n"
        f"Recent unpushed commits:\n{unpushed_text}"
    )


def _build_body_prompt(context: dict[str, Any], slug: str) -> str:
    return (
        f"Change slug: {slug}\n\n"
        f"Diff patch:\n{context.get('diff_patch', '') or '(empty)'}\n\n"
        "Write the pull request description."
    )


def _correction_message(*, naming: PrNaming | None, invalid_json: bool) -> str:
    if invalid_json:
        return (
            "Your previous response was invalid. Return JSON only with keys "
            "slug, title, commit_message, body. slug and title must be lowercase "
            "snake_case between 3 and 48 characters."
        )
    return (
        "Your JSON was valid, but body must not list files or diff stats. "
        "Rewrite body as 1-3 sentences explaining what the change does and why. "
        "Keep slug, title, and commit_message the same."
    )


def _generate_prose_body(*, client: Any, context: dict[str, Any], slug: str) -> str:
    return _complete_text(
        client,
        [
            {"role": "system", "content": _BODY_SYSTEM_PROMPT},
            {"role": "user", "content": _build_body_prompt(context, slug)},
        ],
    )


def _derive_slug_from_context(context: dict[str, Any]) -> str:
    changed_files = context.get("changed_files", [])
    app_files = [
        path
        for path in changed_files
        if path.startswith("app/") and not path.endswith("__init__.py")
    ]
    non_test = [path for path in changed_files if not path.startswith("tests/")]
    candidates = app_files or non_test or changed_files

    stems: list[str] = []
    for path in candidates[:3]:
        stem = sanitize_slug(PurePosixPath(path).stem)
        if stem and stem not in stems:
            stems.append(stem)

    slug = sanitize_slug("_".join(stems) if stems else "code_update")
    if not is_valid_slug(slug):
        return "code_update"
    return slug


def _build_fallback_naming(context: dict[str, Any]) -> PrNaming:
    slug = _derive_slug_from_context(context)
    unique_slug = ensure_unique_branch_slug(slug)
    body = _fallback_body(unique_slug, context)
    if unique_slug != slug:
        body = f"{body} (branch suffix adjusted for uniqueness.)"
    return PrNaming(
        slug=unique_slug,
        title=unique_slug,
        commit_message=unique_slug,
        body=body,
        branch=f"feature/{unique_slug}",
    )


def _fallback_body(slug: str, context: dict[str, Any] | None) -> str:
    topic = slug.replace("_", " ")
    changed_files = (context or {}).get("changed_files", [])
    if not changed_files:
        return f"This change implements {topic}."
    return f"This change implements {topic} across the updated project files."


def _replace_body(naming: PrNaming, body: str) -> PrNaming:
    return PrNaming(
        slug=naming.slug,
        title=naming.title,
        commit_message=naming.commit_message,
        body=body,
        branch=naming.branch,
    )


def _parse_naming(
    raw: str,
    *,
    context: dict[str, Any] | None = None,
    use_fallback_body: bool = False,
) -> PrNaming | None:
    payload = extract_json(raw)
    if not isinstance(payload, dict):
        return None

    slug = sanitize_slug(str(payload.get("slug", "")))
    title = sanitize_slug(str(payload.get("title", slug)))
    if not is_valid_slug(slug) or not is_valid_slug(title):
        return None

    commit_message = str(payload.get("commit_message", slug)).strip()
    if not commit_message:
        commit_message = slug
    if commit_message.splitlines()[0].strip() != slug:
        commit_message = slug if "\n" not in commit_message else f"{slug}\n{commit_message.splitlines()[-1].strip()}"

    body = str(payload.get("body", "")).strip()
    if not body:
        body = _fallback_body(slug, context)
    elif use_fallback_body and looks_like_file_list_body(body):
        body = _fallback_body(slug, context)

    unique_slug = ensure_unique_branch_slug(slug)
    final_title = unique_slug
    final_commit = unique_slug if unique_slug == slug else unique_slug
    if unique_slug != slug:
        body = f"{body} (branch suffix adjusted for uniqueness.)"
    return PrNaming(
        slug=unique_slug,
        title=final_title,
        commit_message=final_commit,
        body=body,
        branch=f"feature/{unique_slug}",
    )
