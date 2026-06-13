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
        request = _request_payload(event)
        command = _command_text(event, request)
        session_id = _session_id(event, request)
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
        return self._emit_resolved_context(context, parked.status)

    def flush_resolved(self, parked_action_id: str) -> dict[str, JsonValue]:
        context = self._peek(parked_action_id)
        if context is None:
            return {"flushed": False, "reason": "unknown_parked_action"}
        try:
            parked = self.engine.queue.get(parked_action_id)
        except KeyError:
            return {"flushed": False, "reason": "unknown_parked_action"}
        if parked.status == "pending":
            return {"flushed": False, "reason": "still_pending"}
        consumed = self._recall(parked_action_id)
        if consumed is None:
            return {"flushed": False, "reason": "unknown_parked_action"}
        result = self._emit_resolved_context(consumed, parked.status)
        return {"flushed": True, "status": result["status"]}

    # ------------------------------------------------------------- parked map
    def _remember(self, parked_action_id: str, context: dict[str, JsonValue]) -> None:
        if self.store is not None:
            self.store.kv_set(_PARKED_PREFIX + parked_action_id, json.dumps(context))
        else:
            self._parked[parked_action_id] = context

    def _peek(self, parked_action_id: str) -> Optional[dict[str, JsonValue]]:
        if self.store is None:
            return self._parked.get(parked_action_id)
        return _parse_context(self.store.kv_get(_PARKED_PREFIX + parked_action_id))

    def _recall(self, parked_action_id: str) -> Optional[dict[str, JsonValue]]:
        """Read-and-consume the parked context (it resolves exactly once)."""
        if self.store is None:
            return self._parked.pop(parked_action_id, None)
        parsed = _parse_context(self.store.kv_get(_PARKED_PREFIX + parked_action_id))
        if parsed is None:
            return None
        self.store.kv_set(_PARKED_PREFIX + parked_action_id, "")  # consume-once tombstone
        return parsed

    def _emit_resolved_context(self, context: dict[str, JsonValue], status: str) -> dict[str, JsonValue]:
        effective = status == "approved"
        self._resolve(
            str(context["request_id"]),
            approved=effective,
            reason="operator_{0}".format(status),
            receipt_id=str(context["receipt_id"]),
        )
        self.engine.record(
            str(context["receipt_id"]),
            ExecutionOutcome(
                status=ExecutionStatus.success if effective else ExecutionStatus.failure,
                notes="exec approval {0} by operator".format(status),
            ),
            capability_id=str(context["capability_id"]),
            session_id=str(context["session_id"]),
        )
        return {"resolved": True, "status": status}

    def _resolve(self, request_id: str, *, approved: bool, reason: str, receipt_id: str) -> None:
        decision = "allow-once" if approved else "deny"
        self.emit(
            {
                "type": "exec.approval.resolve",
                "method": "exec.approval.resolve",
                "params": {"id": request_id, "decision": decision},
                "id": request_id,
                "decision": decision,
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


def _request_payload(event: dict[str, JsonValue]) -> dict[str, JsonValue]:
    request = event.get("request")
    return request if isinstance(request, dict) else event


def _command_text(event: dict[str, JsonValue], request: dict[str, JsonValue]) -> str:
    for value in (
        request.get("command"),
        request.get("commandText"),
        request.get("commandPreview"),
        event.get("command"),
    ):
        text = _text(value)
        if text is not None:
            return text
    return ""


def _session_id(event: dict[str, JsonValue], request: dict[str, JsonValue]) -> str:
    for value in (event.get("session_id"), request.get("sessionKey"), request.get("agentId")):
        text = _text(value)
        if text is not None:
            return text
    return "openclaw.default"


def _parse_context(raw: Optional[str]) -> Optional[dict[str, JsonValue]]:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None
