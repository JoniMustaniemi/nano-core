from __future__ import annotations

from app.assistant.pending import pending_interactions
from app.config import get_settings
from app.proactive.store import proactive_store
from app.runtime.active_timers import serialize_active_stopwatches, serialize_active_timers
from app.runtime.activity import activity
from app.runtime.status_copy import client_copy_payload


def build_runtime_snapshot() -> dict[str, object]:
    """Compose the full runtime snapshot exposed to clients and APIs."""
    hub = activity.snapshot()
    settings = get_settings()
    pending = pending_interactions.get(settings.proactive_conversation_id)
    pending_kind = pending.kind if pending is not None else None
    return {
        **hub,
        "copy": client_copy_payload(),
        "active_timers": serialize_active_timers(),
        "active_stopwatches": serialize_active_stopwatches(),
        "proactive": proactive_store.snapshot(),
        "pending": {"kind": pending_kind},
    }
