from __future__ import annotations

from pathlib import Path

from zeus_agent.model_runtime.provider_catalog import provider_catalog
from zeus_agent.session_runtime import SessionStore


def entry_status_payload(home: Path) -> dict[str, object]:
    store = SessionStore(home)
    sessions = store.list_sessions()
    providers = provider_catalog()
    return {
        "zeus_persona": "active",
        "default_profile": "chat",
        "session_count": len(sessions),
        "provider_profile_count": len(providers),
        "live_production_claimed": False,
        "objective_controls_available": True,
        "leases_required_for_live_surfaces": True,
    }
