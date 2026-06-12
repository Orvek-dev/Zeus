from __future__ import annotations

from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.decision_api_runtime import (
    DecisionContext,
    DecisionRequest,
    GateSurface,
    HostKind,
    ZeusDecisionEngine,
)
from zeus_agent.trust_loop_runtime import (
    ExecutionOutcome,
    ExecutionStatus,
    TrustDecision,
)

from .mapping import map_hermes_tool_call

_COORDINATOR_PRINCIPAL: Final = "agent.hermes"


class HermesGate:
    """hermes pre_tool_call/post_tool_call → decide()/record().

    Principal threading (GAP-4): the coordinator runs as ``agent.hermes``;
    each subagent runs as ``agent.hermes.sub.<id>`` with the coordinator as
    parent — and a child out of its parent's envelope is DENIED, never asked.
    """

    def __init__(self, engine: ZeusDecisionEngine) -> None:
        self.engine = engine

    def pre_tool_call(self, payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
        session_id = _text(payload.get("session_id")) or "hermes.default"
        tool = _text(payload.get("tool")) or _text(payload.get("tool_name")) or "unknown"
        args = payload.get("args")
        if not isinstance(args, dict):
            args = payload.get("tool_input")
        args_dict = args if isinstance(args, dict) else {}
        agent_id = _text(payload.get("agent_id"))
        parent_agent_id = _text(payload.get("parent_agent_id"))

        principal_id = (
            "{0}.sub.{1}".format(_COORDINATOR_PRINCIPAL, agent_id)
            if parent_agent_id is not None and agent_id is not None
            else _COORDINATOR_PRINCIPAL
        )
        mapped = map_hermes_tool_call(tool, args_dict)
        request = DecisionRequest(
            principal_id=principal_id,
            session_id=session_id,
            run_id="run.hermes.{0}".format(_short(session_id)),
            capability_id=mapped.capability_id,
            args=mapped.args,
            context=DecisionContext(
                host=HostKind.hermes,
                surface=GateSurface.hook,
                objective_id=_text(payload.get("objective_id")),
                parent_principal_id=(
                    _COORDINATOR_PRINCIPAL if parent_agent_id is not None else None
                ),
                state_hash=_text(payload.get("state_hash")),
            ),
        )
        response = self.engine.decide(request)
        self.engine.recorder.record_gate_observation(
            run_id=request.run_id,
            host=HostKind.hermes.value,
            surface=GateSurface.hook.value,
            capability_id=mapped.capability_id,
            governed=True,
            decision_receipt_record_id=response.receipt_id,
        )
        if response.decision in {TrustDecision.AUTO, TrustDecision.NOTIFY}:
            action = "allow"
        else:
            action = "block"
        result: dict[str, JsonValue] = {
            "action": action,
            "reason": "[Zeus] {0}: {1}".format(response.decision.value, response.reason),
            "capability_id": mapped.capability_id,
            "receipt_id": response.receipt_id,
            "parked_action_id": response.parked_action_id,
            "principal_id": principal_id,
        }
        if response.decision is TrustDecision.ASK:
            result["retry"] = "reissue_after_operator_replay_approval"
            result["operator_hint"] = (
                "resolve in Zeus control tower or a separate operator terminal; "
                "do not paste Zeus commands into Hermes"
            )
        return result

    def post_tool_call(self, payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
        receipt_id = _text(payload.get("receipt_id"))
        if receipt_id is None:
            return {"recorded": False, "reason": "missing_receipt_id"}
        failed = bool(payload.get("is_error"))
        cost = payload.get("cost_actual_units", 0)
        outcome_record_id = self.engine.record(
            receipt_id,
            ExecutionOutcome(
                status=ExecutionStatus.failure if failed else ExecutionStatus.success,
                cost_actual_units=int(cost) if isinstance(cost, (int, float)) and cost > 0 else 0,
            ),
            capability_id=_text(payload.get("capability_id")),
            session_id=_text(payload.get("session_id")),
            objective_id=_text(payload.get("objective_id")),
        )
        return {"recorded": True, "outcome_record_id": outcome_record_id}


def _short(value: str) -> str:
    cleaned = "".join(ch for ch in value if ch.isalnum())
    return (cleaned[:12] or "default").lower()


def _text(value: JsonValue | None) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
