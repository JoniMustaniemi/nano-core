from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    args_schema: dict[str, str]
    handler: Callable[[dict[str, Any]], str]

    def prompt_line(self) -> str:
        args = ", ".join(self.args_schema)
        return f"- {self.name}({args}): {self.description}"
