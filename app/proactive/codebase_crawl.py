from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from app.assistant.rules.parsing import extract_json
from app.config import get_settings
from app.memory import codebase_index
from app.proactive.codebase_files import file_content_hash, list_all_app_files
from app.proactive.types import ProactiveOffer
from app.runtime.activity import activity
from app.runtime.status_copy import SCANNED_SOURCE_FILE_TITLE
from app.tools.files import read_text_file


class CodebaseCrawlService:
    """Slow one-file-at-a-time codebase scan using the local model."""

    def scan_next_file(self, *, client: Any) -> ProactiveOffer | None:
        settings = get_settings()
        if not settings.idle_examine_enabled:
            return None

        for _ in range(settings.codebase_crawl_files_per_tick):
            offer = self._scan_one_file(client=client)
            if offer is not None:
                return offer
        return None

    def _scan_one_file(self, *, client: Any) -> ProactiveOffer | None:
        settings = get_settings()
        all_paths = list_all_app_files()
        if not all_paths:
            return None

        path = codebase_index.pick_next_scan_target(all_paths=all_paths)
        if path is None:
            return None

        try:
            text = read_text_file(path)
        except (OSError, ValueError):
            return None

        if len(text) > settings.self_improve_max_file_chars:
            text = text[: settings.self_improve_max_file_chars]

        messages = [
            {
                "role": "system",
                "content": (
                    "You review one Python source file from Nano's codebase. "
                    "Return JSON only: "
                    '{"summary": "...", "suggestion": "..."|null, "confidence": "low|medium|high"}'
                ),
            },
            {
                "role": "user",
                "content": f"Path: {path}\n\n{text}",
            },
        ]
        raw = cast(str, client.complete(messages=messages)).strip()
        payload = extract_json(raw)
        summary = str(payload.get("summary", "")).strip()
        suggestion_raw = payload.get("suggestion")
        suggestion = str(suggestion_raw).strip() if suggestion_raw else None
        confidence = str(payload.get("confidence", "low")).lower()

        content_hash = file_content_hash(path)
        codebase_index.upsert_scan_result(
            path=path,
            content_hash=content_hash,
            summary=summary,
            last_suggestion=suggestion,
            last_confidence=confidence or None,
        )
        activity.log(
            title=SCANNED_SOURCE_FILE_TITLE,
            detail=path,
            source="proactive.codebase_crawl",
        )

        if not suggestion or confidence == "low":
            return None

        goal = suggestion
        return ProactiveOffer(
            kind="self_improvement_suggestion",
            title="Codebase improvement idea",
            summary=suggestion,
            payload={"goal": goal, "files": [path], "summary": summary},
            created_at=datetime.now(UTC),
        )
