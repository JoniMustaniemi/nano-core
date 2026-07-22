from __future__ import annotations

import os


def uvicorn_reload_enabled() -> bool:
    """Return True when the dev server was started with Uvicorn auto-reload."""
    return os.environ.get("NANO_UVICORN_RELOAD") == "1"
