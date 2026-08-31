from __future__ import annotations

from app.assistant.pending import pending_interactions
from app.config import get_settings
from app.deploy.update_state import update_store
from app.proactive.store import proactive_store
from app.runtime.activity import activity
from app.runtime.boot_state import boot_store
from app.runtime.location import location_store
from app.runtime.status_copy import client_copy_payload
from app.system.specs import serialize_system_metrics
from app.timers.serialization import serialize_active_stopwatches, serialize_active_timers


def build_runtime_snapshot() -> dict[str, object]:
    """Compose the full runtime snapshot exposed to clients and APIs."""
    hub = activity.snapshot()
    settings = get_settings()
    pending = pending_interactions.get("default") or pending_interactions.get(
        settings.proactive_conversation_id
    )
    pending_kind = pending.kind if pending is not None else None
    update_snapshot = update_store.snapshot()
    boot_snapshot = boot_store.snapshot()
    return {
        **hub,
        "copy": client_copy_payload(),
        "boot": {
            "id": boot_snapshot.id,
            "booted_at": boot_snapshot.booted_at,
            "reboot_pending": boot_snapshot.reboot_pending,
            "restart_pending": boot_snapshot.restart_pending,
        },
        "active_timers": serialize_active_timers(),
        "active_stopwatches": serialize_active_stopwatches(),
        "proactive": proactive_store.snapshot(),
        "pending": {"kind": pending_kind},
        "update": {
            "available": update_snapshot.available,
            "commits_behind": update_snapshot.commits_behind,
            "remote_sha": (update_snapshot.remote_sha[:7] if update_snapshot.remote_sha else None),
        },
        "system": serialize_system_metrics(),
        "location": location_store.snapshot(),
    }
