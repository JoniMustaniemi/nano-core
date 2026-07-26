from __future__ import annotations

from collections.abc import Callable
from threading import Thread
from typing import Any


def run_background(fn: Callable[[], Any], *, label: str) -> Thread:
    """Run a callable on a daemon background thread."""
    thread = Thread(target=fn, name=label, daemon=True)
    thread.start()
    return thread
