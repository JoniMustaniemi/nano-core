from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol


class LLMClient(Protocol):
    def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str: ...
