from __future__ import annotations

from typing import Any

from app.proactive.codebase_crawl import CodebaseCrawlService
from app.proactive.codebase_files import walk_app_files
from app.proactive.types import ProactiveOffer

__all__ = ["CodebaseCrawlService", "CodebaseExamineService", "walk_app_files"]


class CodebaseExamineService(CodebaseCrawlService):
  """Backward-compatible alias for the slow codebase crawl."""

  def run(self, *, client: Any) -> ProactiveOffer | None:
    return self.scan_next_file(client=client)
