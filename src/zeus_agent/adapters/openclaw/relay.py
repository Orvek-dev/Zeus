from __future__ import annotations

import json
from typing import Callable, Final, Optional

from pydantic import JsonValue

from zeus_agent.command_risk_runtime import classify_command
from zeus_agent.capability_registry_runtime import SideEffectClass
from zeus_agent.decision_api_runtime import (
    DecisionContext,
    DecisionRequest,
    GateSurface,
    HostKind,
    ZeusDecisionEngine,
)
from zeus_agent.security.credentials import contains_secret_material
from zeus_agent.trust_loop_runtime import (
    ExecutionOutcome,
    ExecutionStatus,
    Reversibility,
    SQLiteControlPlaneStore,
    TrustDecision,
)

_PRINCIPAL: Final = "agent.openclaw"
_PARKED_PREFIX: Final = "openclaw.parked."
_TERMINAL_BY_RISK: Final[dict[tuple[SideEffectClass, Reversibility], str]] = {
    (SideEffectClass.none, Reversibility.reversible): "terminal.run.read",
    (SideEffectClass.local_write, Reversibility.compensable): "terminal.run.local",
    (SideEffectClass.account_write, Reversibility.compensable): "terminal.run.package",
    (SideEffectClass.account_write, Reversibility.irreversible): "terminal.run.external",
}

EmitResolution = Callable[[dict[str, JsonValue]], None]


class ExecApprovalRelay:
    """``exec.approval.requested`` → decide → ``exec.approval.resolve``.

    Zeus is the operator client: allow and deny resolve immediately; ASK
    parks in the Zeus queue and resolves when the human does (the agent waits
    — pre-call enforcement, not an after-the-fact alert). The transport that
    carries events is injected; this engine is transport-agnostic.
    """

    def __init__(
        self,
        *,
        engine: ZeusDecisionEngine,
        emit: EmitResolution,
        store: Optional[SQLiteControlPlaneStore] = None,
    ) -> None:
        self.engine = engine
        self.emit = emit
        # The parked → OpenClaw-request mapping must outlive this relay process:
        # the SQLite queue keeps the parked ACTION, but without this mapping a
        # restarted relay can't tell the host its approval resolved. With a
        # store it is durable and any relay instance (sharing the store + a live
        # transport) can resolve; the in-memory dict is the no-store fallback.
        self.store = store
        self._parked: dict[str, dict[str, JsonValue]] = {}

    # ----------------------------------------------------------------- ingest
    def handle_approval_request(self, event: dict[str, JsonValue]) -> dict[str, JsonValue]:
        request_id = str(event.get("id", event.get("request_id", ""))).strip()
        command = str(event.get("command", "")).strip()
        session_id = str(event.get("session_id", "openclaw.default")).strip()
        if not request_id or not command:
            return {"handled": False, "reason": "malformed_event"}

        risk = classify_command(command)
        capability_id = _TERMINAL_BY_RISK.get(
            (risk.side_effect, risk.reversibility), "terminal.run.external"
        )
        args: dict[str, JsonValue] = {"command": command, "command_risk": list(risk.reasons)}
        if contains_secret_material(command):
            args["secret_material_in_command"] = True
        response = self.engine.decide(
            DecisionRequest(
                principal_id=_PRINCIPAL,
                session_id=session_id,
                run_id="run.openclaw.{0}".format(_short(session_id)),
                capability_id=capability_id,
                args=args,
                context=DecisionContext(
                    host=HostKind.openclaw,
                    surface=GateSurface.hook,
                    objective_id=_text(event.get("objective_id")),
                ),
            )
        )
        self.engine.recorder.record_gate_observation(
            run_id="run.openclaw.{0}".format(_short(session_id)),
            host=HostKind.openclaw.value,
            surface=GateSurface.hook.value,
            capability_id=capability_id,
            governed=True,
            decision_receipt_record_id=response.receipt_id,
        )
        if response.decision in {TrustDecision.AUTO, TrustDecision.NOTIFY}:
            self._resolve(request_id, approved=True, reason=response.reason, receipt_id=response.receipt_id)
            return {
                "handled": True,
                "resolution": "allow",
                "receipt_id": response.receipt_id,
                "capability_id": capability_id,
            }
        if response.decision is TrustDecision.DENY:
            self._resolve(request_id, approved=False, reason=response.reason, receipt_id=response.receipt_id)
            return {
                "handled": True,
                "resolution": "deny",
                "receipt_id": response.receipt_id,
                "capability_id": capability_id,
            }
        assert response.parked_action_id is not None
        self._remember(
            response.parked_action_id,
            {
                "request_id": request_id,
                "receipt_id": response.receipt_id,
                "session_id": session_id,
                "capability_id": capability_id,
            },
        )
        return {
            "handled": True,
            "resolution": "pending",
            "parked_action_id": response.parked_action_id,
            "receipt_id": response.receipt_id,
            "capability_id": capability_id,
        }

    # ---------------------------------------------------------------- operator
    def resolve_parked(self, parked_action_id: str, *, approved: bool) -> dict[str, JsonValue]:
        context = self._recall(parked_action_id)
        if context is None:
            return {"resolved": False, "reason": "unknown_parked_action"}
        parked = self.engine.queue.resolve(parked_action_id, approved=approved)
        # what reaches the host is the QUEUE's verdict, not the caller's
        # intent: an expired/superseded park resolves approved=False even if
        # the operator clicked approve after the deadline (TTL fail-closed).
        effective = approved and parked.status == "approved"
        self._resolve(
            str(context["request_id"]),
            approved=effective,
            reason="operator_{0}".format(parked.status),
            receipt_id=str(context["receipt_id"]),
        )
        self.engine.record(
            str(context["receipt_id"]),
            ExecutionOutcome(
                status=ExecutionStatus.success if effective else ExecutionStatus.failure,
                notes="exec approval {0} by operator".format(parked.status),
            ),
            capability_id=str(context["capability_id"]),
            session_id=str(context["session_id"]),
        )
        return {"resolved": True, "status": parked.status}

    # ------------------------------------------------------------- parked map
    def _remember(self, parked_action_id: str, context: dict[str, JsonValue]) -> None:
        if self.store is not None:
            self.store.kv_set(_PARKED_PREFIX + parked_action_id, json.dumps(context))
        else:
            self._parked[parked_action_id] = context

    def _recall(self, parked_action_id: str) -> Optional[dict[str, JsonValue]]:
        """Read-and-consume the parked context (it resolves exactly once)."""
        if self.store is None:
            return self._parked.pop(parked_action_id, None)
        raw = self.store.kv_get(_PARKED_PREFIX + parked_action_id)
        if not raw:  # absent or already-consumed tombstone
            return None
        try:
            parsed = json.loads(raw)
        except ValueError:
            return None
        self.store.kv_set(_PARKED_PREFIX + parked_action_id, "")  # consume-once tombstone
        return parsed if isinstance(parsed, dict) else None

    def _resolve(self, request_id: str, *, approved: bool, reason: str, receipt_id: str) -> None:
        self.emit(
            {
                "type": "exec.approval.resolve",
                "id": request_id,
                "approved": approved,
                "reason": "[Zeus] {0}".format(reason),
                "receipt_id": receipt_id,
            }
        )


def _short(value: str) -> str:
    cleaned = "".join(ch for ch in value if ch.isalnum())
    return (cleaned[:12] or "default").lower()


def _text(value: JsonValue | None) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
