from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class ProactiveOffer:
    """A topic Nano wants to discuss with the user after presence confirmation."""

    kind: str
    title: str
    summary: str
    payload: dict[str, Any]
    created_at: datetime

    def to_json(self) -> str:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> ProactiveOffer:
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}

        parsed_created_at = datetime.now(UTC)
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            try:
                parsed = datetime.fromisoformat(created_at)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                parsed_created_at = parsed
            except ValueError:
                pass

        payload = data.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}

        return cls(
            kind=str(data.get("kind", "")),
            title=str(data.get("title", "")),
            summary=str(data.get("summary", "")),
            payload=dict(payload),
            created_at=parsed_created_at,
        )
