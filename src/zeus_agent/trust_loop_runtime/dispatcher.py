from __future__ import annotations

import json
from typing import Callable, Optional

from pydantic import JsonValue

from zeus_agent.kernel.authority import ApprovalReceipt, AuthorityContext
from zeus_agent.kernel.broker import CapabilityBroker
from zeus_agent.kernel.capabilities import CapabilityGraph
from zeus_agent.runtime_lease import RuntimeIntakeRequest, RuntimeKind, RuntimeLease, RuntimeLeaseBuilder
from zeus_agent.security.credentials import contains_secret_material

from .ledger import SQLiteEvidenceLedger
from .models import (
    ApprovalEnvelope,
    DecisionReceipt,
    Reversibility,
    TrustDecision,
    TrustLoopAction,
    TrustPolicyProfile,
)
from .policy import TrustDecisionEngine, TrustPolicyOutcome
from .skill_manifest import SkillManifest

Handler = Callable[[dict[str, JsonValue]], dict[str, JsonValue]]


class GovernedExecutionDispatcher:
    def __init__(
        self,
        *,
        capability_graph: CapabilityGraph,
        handlers: dict[str, Handler],
        ledger: SQLiteEvidenceLedger,
        policy: TrustPolicyProfile = TrustPolicyProfile.cautious,
        skill_manifest: SkillManifest | None = None,
    ) -> None:
        self._capability_graph = capability_graph
        self._handlers = dict(handlers)
        self.ledger = ledger
        self._policy = TrustDecisionEngine(policy)
        self._skill_manifest = skill_manifest

    def dispatch(
        self,
        action: TrustLoopAction,
        *,
        lease: RuntimeLease | None,
        approval: ApprovalReceipt | None = None,
        approval_envelope: ApprovalEnvelope | None = None,
    ) -> DecisionReceipt:
        if self._skill_manifest is not None and not self._skill_manifest.allows(action.capability_id):
            return self._blocked(action, TrustDecision.DENY, "skill_manifest_capability_blocked")
        if self._capability_graph.descriptor_for(action.capability_id) is None:
            return self._blocked(action, TrustDecision.DENY, "unknown_capability")
        runtime_kind = _runtime_kind_for(action.capability_id)
        if runtime_kind is None:
            return self._blocked(action, TrustDecision.DENY, "unsupported_runtime_kind")
        authorization = RuntimeLeaseBuilder().authorize(
            lease,
            RuntimeIntakeRequest(
                runtime_kind=runtime_kind,
                capability_id=action.capability_id,
                credential_scope=action.credential_scope,
                network_host=action.network_host,
                live_network=action.live_network,
                budget_required=action.budget.requested_units,
                evidence_target=action.evidence_target,
            ),
        )
        if authorization.decision == "blocked" or authorization.authority is None:
            return self._blocked(action, TrustDecision.DENY, authorization.reason)
        approval_result = _approval_result(
            action=action,
            authority=authorization.authority,
            approval=approval,
            approval_envelope=approval_envelope,
        )
        policy = self._policy.evaluate(
            action,
            approval_bound=approval_result.bound,
            undo_proven=approval_result.undo_proven,
        )
        if _must_stop_before_execution(policy, approval_result.bound):
            return self._blocked(action, policy.decision, policy.reason)
        return self._execute(
            action=action,
            authority=authorization.authority,
            approval=approval,
            approval_result=approval_result,
            policy=policy,
        )

    def _execute(
        self,
        *,
        action: TrustLoopAction,
        authority: AuthorityContext,
        approval: ApprovalReceipt | None,
        approval_result: "_ApprovalResult",
        policy: TrustPolicyOutcome,
    ) -> DecisionReceipt:
        broker = CapabilityBroker(self._capability_graph, handlers=self._handlers)
        broker_response = broker.dispatch(
            action.capability_id,
            _broker_payload(action),
            authority,
            approval_receipts=() if approval is None else (approval,),
            criterion_id=action.criterion_id,
        )
        broker_decision = str(broker_response.get("decision"))
        result = _json_dict_or_none(broker_response.get("result"))
        if broker_decision != "allowed":
            return self._blocked(
                action,
                TrustDecision.DENY,
                str(broker_response.get("reason", "broker_blocked")),
                broker_evidence_bound=isinstance(broker_response.get("evidence"), dict),
            )
        event = self.ledger.append(
            kind="decision_receipt",
            run_id=action.run_id,
            payload={
                "action_id": action.action_id,
                "capability_id": action.capability_id,
                "decision": policy.decision.value,
                "policy_reason": policy.reason,
                "broker_evidence": _json_dict_or_none(broker_response.get("evidence")),
                "result": result,
            },
        )
        return DecisionReceipt(
            receipt_id=_receipt_id("trust.receipt", action.action_id),
            action_id=action.action_id,
            run_id=action.run_id,
            capability_id=action.capability_id,
            decision=policy.decision,
            handler_executed=True,
            broker_evidence_bound=True,
            approval_bound=approval_result.bound,
            evidence_record_id=event.record_id,
            cleanup_receipt_id=_receipt_id("trust.cleanup", action.action_id),
            undo_token_id=approval_result.undo_token_id,
            result=result,
            no_secret_echo=not contains_secret_material(json.dumps(result, sort_keys=True)),
        )

    def _blocked(
        self,
        action: TrustLoopAction,
        decision: TrustDecision,
        reason: str,
        *,
        broker_evidence_bound: bool = False,
    ) -> DecisionReceipt:
        event = self.ledger.append(
            kind="decision_receipt",
            run_id=action.run_id,
            payload={
                "action_id": action.action_id,
                "capability_id": action.capability_id,
                "decision": decision.value,
                "blocked_reason": reason,
            },
        )
        return DecisionReceipt(
            receipt_id=_receipt_id("trust.receipt", action.action_id),
            action_id=action.action_id,
            run_id=action.run_id,
            capability_id=action.capability_id,
            decision=decision,
            blocked_reason=reason,
            handler_executed=False,
            broker_evidence_bound=broker_evidence_bound,
            evidence_record_id=event.record_id,
        )


class _ApprovalResult:
    def __init__(
        self,
        *,
        bound: bool,
        undo_proven: bool,
        undo_token_id: Optional[str],
    ) -> None:
        self.bound = bound
        self.undo_proven = undo_proven
        self.undo_token_id = undo_token_id


def _approval_result(
    *,
    action: TrustLoopAction,
    authority: AuthorityContext,
    approval: ApprovalReceipt | None,
    approval_envelope: ApprovalEnvelope | None,
) -> _ApprovalResult:
    if approval is None:
        return _ApprovalResult(bound=False, undo_proven=False, undo_token_id=None)
    try:
        approval.assert_within_authority(authority)
    except ValueError:
        return _ApprovalResult(bound=False, undo_proven=False, undo_token_id=None)
    if action.capability_id not in set(approval.approved_capabilities):
        return _ApprovalResult(bound=False, undo_proven=False, undo_token_id=None)
    if approval_envelope is None:
        return _ApprovalResult(bound=True, undo_proven=False, undo_token_id=None)
    if approval_envelope.capability_id != action.capability_id:
        return _ApprovalResult(bound=False, undo_proven=False, undo_token_id=None)
    undo_plan = approval_envelope.undo_plan
    undo_proven = action.reversibility is Reversibility.irreversible or undo_plan is not None
    return _ApprovalResult(
        bound=True,
        undo_proven=undo_proven,
        undo_token_id=None if undo_plan is None else undo_plan.plan_id,
    )


def _must_stop_before_execution(policy: TrustPolicyOutcome, approval_bound: bool) -> bool:
    return _STOP_RULES[policy.decision](approval_bound)


def _runtime_kind_for(capability_id: str) -> RuntimeKind | None:
    if capability_id.startswith("provider."):
        return "provider"
    if capability_id.startswith("mcp."):
        return "mcp"
    if capability_id.startswith("gateway."):
        return "gateway"
    if capability_id.startswith("terminal."):
        return "terminal"
    if capability_id.startswith("sandbox."):
        return "sandbox"
    if capability_id.startswith("browser."):
        return "browser"
    if capability_id.startswith("web."):
        return "web"
    if capability_id.startswith("github."):
        return "github"
    if capability_id.startswith("plugin."):
        return "plugin"
    return None


def _broker_payload(action: TrustLoopAction) -> dict[str, JsonValue]:
    payload = dict(action.payload)
    if action.credential_scope is not None:
        payload["credential_scope"] = action.credential_scope
    if action.network_host is not None:
        payload["network_host"] = action.network_host
    return payload


def _json_dict_or_none(value: JsonValue | None) -> dict[str, JsonValue] | None:
    if not isinstance(value, dict):
        return None
    try:
        return json.loads(json.dumps(value))
    except (TypeError, ValueError):
        return None


def _receipt_id(prefix: str, action_id: str) -> str:
    return "{0}.{1}".format(prefix, action_id.replace(".", "_"))


_STOP_RULES: dict[TrustDecision, Callable[[bool], bool]] = {
    TrustDecision.AUTO: lambda _approval_bound: False,
    TrustDecision.NOTIFY: lambda _approval_bound: False,
    TrustDecision.ASK: lambda approval_bound: not approval_bound,
    TrustDecision.DENY: lambda _approval_bound: True,
}
