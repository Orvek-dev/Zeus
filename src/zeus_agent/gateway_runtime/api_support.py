from __future__ import annotations

from pathlib import Path
from typing import Final, assert_never

from zeus_agent.gateway_runtime.models import ExcludingAllowedReason, GatewayReason
from zeus_agent.gateway_runtime.session_store import SQLiteGatewaySessionStore

BLOCKED_SESSION_ID: Final = "g006.blocked.session"
BLOCKED_RUN_ID: Final = "g006.blocked.run"
BLOCKED_GOAL_CONTRACT_ID: Final = "g006.blocked.goal"


class GatewayApiRuntimeConfigError(RuntimeError):
    pass


def select_store(
    db_path: Path | None,
    store: SQLiteGatewaySessionStore | None,
) -> SQLiteGatewaySessionStore:
    if db_path is not None and store is not None:
        raise GatewayApiRuntimeConfigError("choose db_path or store, not both")
    if store is not None:
        return store
    if db_path is None:
        raise GatewayApiRuntimeConfigError("db_path or store is required")
    return SQLiteGatewaySessionStore(db_path)


def excluding_allowed_reason(reason: GatewayReason) -> ExcludingAllowedReason:
    match reason:
        case "allowed":
            raise GatewayApiRuntimeConfigError("blocked response used allowed reason")
        case (
            "unauthenticated"
            | "non_loopback_blocked"
            | "webhook_blocked"
            | "external_delivery_blocked"
            | "standing_order_blocked"
            | "malformed_request"
            | "idempotency_conflict"
        ):
            return reason
        case unreachable:
            assert_never(unreachable)
