from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, cast

from app.assistant.agent_rules import extract_json
from app.tools.git_github import ensure_unique_branch_slug


_SLUG_PATTERN = re.compile(r"^[a-z0-9_]{3,48}$")


@dataclass(frozen=True, slots=True)
class PrNaming:
    slug: str
    title: str
    commit_message: str
    body: str
    branch: str


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
        raw = cast(
            str,
            client.complete(
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ]
            ),
        ).strip()
        naming = _parse_naming(raw)
        if naming is not None:
            return naming

        correction = (
            "Your previous response was invalid. Return JSON only with keys "
            'slug, title, commit_message, body. slug and title must be lowercase '
            "snake_case between 3 and 48 characters."
        )
        raw_retry = cast(
            str,
            client.complete(
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": correction},
                ]
            ),
        ).strip()
        naming = _parse_naming(raw_retry)
        if naming is None:
            raise RuntimeError("Could not generate valid pull request naming from the diff.")
        return naming


_SYSTEM_PROMPT = (
    "You name git branches and pull requests from code diffs. "
    "Return JSON only with keys slug, title, commit_message, body. "
    "slug and title must be lowercase snake_case using only a-z, 0-9, and underscores, "
    "3 to 48 characters. slug must describe the code change from the diff. "
    "commit_message subject must equal slug; an optional body line may follow after a blank line. "
    "body is a 1-3 sentence pull request summary in normal prose."
)


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
        "Name this change for a git feature branch and pull request.\n\n"
        f"Changed files:\n{files_text}\n\n"
        f"Diff stat:\n{context.get('diff_stat', '') or '(empty)'}\n\n"
        f"Diff patch:\n{context.get('diff_patch', '') or '(empty)'}\n\n"
        f"Recent unpushed commits:\n{unpushed_text}"
    )


def _parse_naming(raw: str) -> PrNaming | None:
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

    body = str(payload.get("body", "")).strip() or f"Changes for {slug.replace('_', ' ')}."
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
