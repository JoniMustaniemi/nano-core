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
    announcement: str | None = None
    keywords: tuple[str, ...] = ()
    ui_label: str | None = None
    ui_message: str | None = None
    ui_category: str | None = None
    ui_description: str = ""

    def prompt_line(self) -> str:
        """
        Build line.

        Returns:
            Generated or formatted string value.
        """
        args = ", ".join(self.args_schema)
        return f"- {self.name}({args}): {self.description}"

    @property
    def has_ui_command(self) -> bool:
        return (
            self.ui_label is not None
            and self.ui_message is not None
            and self.ui_category is not None
        )
