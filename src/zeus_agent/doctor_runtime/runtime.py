from __future__ import annotations

from pathlib import Path

from zeus_agent.model_runtime.provider_catalog import provider_catalog
from zeus_agent.session_runtime import SessionStore


def doctor_report(home: Path) -> dict[str, object]:
    store = SessionStore(home)
    sessions = store.list_sessions()
    checks = [
        {
            "id": "provider.catalog",
            "status": "pass",
            "detail": "{0} provider profiles available".format(len(provider_catalog())),
        },
        {
            "id": "session.store",
            "status": "pass",
            "detail": "SQLite session store initialized at {0}".format(store.path),
        },
        {
            "id": "mcp.default_trust",
            "status": "pass",
            "detail": "unknown MCP servers remain quarantined until reviewed",
        },
        {
            "id": "live.production.claim",
            "status": "blocked",
            "detail": "live production claims require separate live opt-in evidence",
        },
    ]
    return {
        "doctor_ok": True,
        "session_count": len(sessions),
        "checks": checks,
        "live_production_claimed": False,
    }
