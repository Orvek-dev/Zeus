from __future__ import annotations

import hashlib
import json
from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.decision_api_runtime import (
    DecisionContext,
    DecisionRequest,
    DecisionResponse,
    GateSurface,
    HostKind,
    ZeusDecisionEngine,
)
from zeus_agent.taint_runtime import TaintLabel, is_private_source, is_untrusted_source
from zeus_agent.trust_loop_runtime import (
    ExecutionOutcome,
    ExecutionStatus,
    TrustDecision,
)

from .card import render_card
from .mapping import MappedCall, map_tool_call
from .state import ControlPlaneState

_PRINCIPAL: Final = "agent.claude_code"
_HOOK_EVENT: Final = "PreToolUse"


class ClaudeCodeGate:
    """Gate 0: Claude Code PreToolUse → decide(); PostToolUse → record().

    JSON in, JSON out, no side effects on the host's behalf — Zeus decides
    and records; Claude Code executes its own tool.
    """

    def __init__(self, state: ControlPlaneState) -> None:
        self.state = state
        self.engine: ZeusDecisionEngine = state.build_engine()

    # ------------------------------------------------------------- PreToolUse
    def handle_pre(self, payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
        session_id = _text(payload.get("session_id")) or "claude-code.default"
        tool_name = _text(payload.get("tool_name")) or "UnknownTool"
        tool_input = payload.get("tool_input")
        tool_input_dict = tool_input if isinstance(tool_input, dict) else {}
        cwd = _text(payload.get("cwd"))

        mapped = map_tool_call(tool_name, tool_input_dict)
        request = DecisionRequest(
            principal_id=_PRINCIPAL,
            session_id=session_id,
            run_id="run.cc.{0}".format(_short(session_id)),
            capability_id=mapped.capability_id,
            args=mapped.args,
            context=DecisionContext(host=HostKind.claude_code, surface=GateSurface.hook),
        )
        # Explainability ("no plain-language template → cannot run silently")
        # is enforced INSIDE decide() now, so the receipt is the truth of the
        # final action — the gate no longer mutates the response after the fact.
        # (Grant burns persist via the write-through store in build_engine —
        # every gate gets that, not just this one.)
        response = self.engine.decide(request)

        self._stamp_taint(session_id, mapped, response, cwd)
        self.engine.recorder.record_gate_observation(
            run_id=request.run_id,
            host=HostKind.claude_code.value,
            surface=GateSurface.hook.value,
            capability_id=mapped.capability_id,
            governed=True,
            decision_receipt_record_id=response.receipt_id,
        )
        if response.decision is not TrustDecision.DENY:
            self.state.push_pending(
                _fingerprint(session_id, tool_name, tool_input_dict), response.receipt_id
            )
        return self._hook_output(mapped, response)

    # ------------------------------------------------------------ PostToolUse
    def handle_post(self, payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
        session_id = _text(payload.get("session_id")) or "claude-code.default"
        tool_name = _text(payload.get("tool_name")) or "UnknownTool"
        tool_input = payload.get("tool_input")
        tool_input_dict = tool_input if isinstance(tool_input, dict) else {}
        receipt_id = self.state.pop_pending(_fingerprint(session_id, tool_name, tool_input_dict))
        if receipt_id is None:
            return {"recorded": False, "reason": "no_pending_receipt"}
        tool_response = payload.get("tool_response")
        failed = isinstance(tool_response, dict) and bool(tool_response.get("is_error"))
        mapped = map_tool_call(tool_name, tool_input_dict)
        outcome_record = self.engine.record(
            receipt_id,
            ExecutionOutcome(
                status=ExecutionStatus.failure if failed else ExecutionStatus.success,
            ),
            capability_id=mapped.capability_id,
            session_id=session_id,
        )
        self.state.save_taint(self.engine.taint, (session_id,))
        return {"recorded": True, "outcome_record_id": outcome_record, "receipt_id": receipt_id}

    # -------------------------------------------------------------- internals
    def _stamp_taint(
        self,
        session_id: str,
        mapped: MappedCall,
        response: DecisionResponse,
        cwd: Optional[str],
    ) -> None:
        """Conservative pre-stamp: if the tool MAY run (not denied) and ingests
        foreign or secret data, the session is tainted from this point on."""
        if response.decision is TrustDecision.DENY:
            return
        stamped = False
        record = self.engine.capabilities.get(mapped.capability_id)
        if is_untrusted_source(mapped.capability_id, record):
            self.engine.taint.stamp(session_id, TaintLabel.untrusted, mapped.capability_id)
            stamped = True
        if is_private_source(mapped.capability_id):
            self.engine.taint.stamp(session_id, TaintLabel.private, mapped.capability_id)
            stamped = True
        path = mapped.args.get("path")
        if (
            mapped.capability_id == "fs.read"
            and isinstance(path, str)
            and cwd
            and not path.startswith(cwd.rstrip("/") + "/")
            and path != cwd
        ):
            self.engine.taint.stamp(session_id, TaintLabel.untrusted, "foreign_file:{0}".format(path))
            stamped = True
        if stamped:
            self.state.save_taint(self.engine.taint, (session_id,))

    def _hook_output(self, mapped: MappedCall, response: DecisionResponse) -> dict[str, JsonValue]:
        record = self.engine.capabilities.get(mapped.capability_id)
        if response.decision in {TrustDecision.AUTO, TrustDecision.NOTIFY}:
            permission, reason = "allow", "[Zeus] {0} ({1})".format(
                response.decision.value, response.reason
            )
        elif response.decision is TrustDecision.DENY:
            permission = "deny"
            reason = "[Zeus] denied: {0} — capability {1}".format(
                response.reason, mapped.capability_id
            )
        else:
            permission = "ask"
            reason = (
                render_card(
                    capability_id=mapped.capability_id,
                    args=mapped.args,
                    record=record,
                    reason=response.reason,
                )
                if record is not None
                else "[Zeus] approval needed: {0} ({1})".format(
                    mapped.capability_id, response.reason
                )
            )
        return {
            "hookSpecificOutput": {
                "hookEventName": _HOOK_EVENT,
                "permissionDecision": permission,
                "permissionDecisionReason": reason,
            },
            "zeus": {
                "capability_id": mapped.capability_id,
                "decision": response.decision.value,
                "reason": response.reason,
                "receipt_id": response.receipt_id,
                "obligations": [item.value for item in response.obligations],
            },
        }


def run_hook_event(
    state: ControlPlaneState,
    event: str,
    payload: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    gate = ClaudeCodeGate(state)
    if event == "post":
        return gate.handle_post(payload)
    return gate.handle_pre(payload)


def _fingerprint(session_id: str, tool_name: str, tool_input: dict[str, JsonValue]) -> str:
    material = json.dumps(
        {"s": session_id, "t": tool_name, "i": tool_input}, sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _short(value: str) -> str:
    cleaned = "".join(ch for ch in value if ch.isalnum())
    return (cleaned[:12] or "default").lower()


def _text(value: JsonValue | None) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
