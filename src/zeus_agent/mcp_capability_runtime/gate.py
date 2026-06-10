from __future__ import annotations

from typing import Final, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.capability_registry_runtime import (
    CapabilityRecord,
    CapabilityStatus,
    SideEffectClass,
    VerbClass,
    import_mcp_capability,
)
from zeus_agent.execution_integrity_runtime import assert_claim, claim_from_decision_receipt
from zeus_agent.kernel.authority import ApprovalReceipt
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.trust_loop_runtime import (
    ActionRisk,
    ApprovalEnvelope,
    BudgetEnvelope,
    DecisionReceipt,
    GovernedExecutionDispatcher,
    Reversibility,
    TrustLoopAction,
)

from .scanner import scan_tool_description

_EVIDENCE_TARGET: Final = "mneme.mcp_capability"
_RISK_BY_EFFECT: Final = {
    SideEffectClass.none: (ActionRisk.low, Reversibility.reversible),
    SideEffectClass.local_write: (ActionRisk.medium, Reversibility.compensable),
    SideEffectClass.account_write: (ActionRisk.high, Reversibility.irreversible),
    SideEffectClass.public_write: (ActionRisk.high, Reversibility.irreversible),
}


class MCPRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    decision: str
    record: Optional[CapabilityRecord] = None
    blocked_reasons: tuple[str, ...] = ()
    injection_markers: tuple[str, ...] = ()


class MCPInvocation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    decision: str
    handler_executed: bool = False
    blocked_reason: Optional[str] = None
    evidence_record_id: Optional[str] = None
    result: Optional[dict[str, JsonValue]] = None


def register_mcp_tool(
    *,
    capability_id: str,
    title: str,
    description: str,
    verb_class: VerbClass,
    schema_hash: str,
    server_ref: str,
) -> MCPRegistration:
    """De-whitelisted registration: any tool may register, but a description with
    injection markers is rejected, and the tool lands quarantined (every call
    needs approval until it earns active status)."""
    markers = scan_tool_description(description)
    if markers:
        return MCPRegistration(
            decision="blocked",
            blocked_reasons=("tool_description_injection",),
            injection_markers=markers,
        )
    record = import_mcp_capability(
        capability_id=capability_id,
        title=title,
        verb_class=verb_class,
        input_summary="mcp tool input",
        output_summary="mcp tool output",
        schema_hash=schema_hash,
        server_ref=server_ref,
    )
    return MCPRegistration(decision="registered", record=record)


def invoke_mcp_tool(
    record: CapabilityRecord,
    *,
    dispatcher: GovernedExecutionDispatcher,
    payload: dict[str, JsonValue],
    lease: RuntimeLease,
    approval: Optional[ApprovalReceipt] = None,
    approval_envelope: Optional[ApprovalEnvelope] = None,
    budget_units: int = 1,
) -> MCPInvocation:
    """Invoke a registered MCP tool through the single broker chokepoint.

    Deprecated → blocked. Quarantined → requires an explicit approval (every
    call), so an unproven third-party tool can never run unattended. Active tools
    follow normal trust-loop policy.
    """
    if record.status is CapabilityStatus.deprecated:
        return MCPInvocation(decision="blocked", blocked_reason="capability_deprecated")
    if record.status is CapabilityStatus.quarantined and approval is None:
        return MCPInvocation(decision="blocked", blocked_reason="quarantined_requires_approval")

    risk, reversibility = _RISK_BY_EFFECT[record.side_effect]
    action = TrustLoopAction(
        action_id="mcp.{0}".format(record.capability_id),
        run_id=lease.run_id,
        goal_contract_id=lease.objective_id,
        criterion_id="REQ-ZEUS-MCP-001:S1",
        capability_id=record.capability_id,
        payload=payload,
        risk=risk,
        reversibility=reversibility,
        budget=BudgetEnvelope(max_units=max(lease.budget_limit, 1), requested_units=budget_units),
        evidence_target=_EVIDENCE_TARGET,
    )
    receipt: DecisionReceipt = dispatcher.dispatch(
        action, lease=lease, approval=approval, approval_envelope=approval_envelope
    )
    assert_claim(claim_from_decision_receipt(receipt, surface="mcp:{0}".format(record.capability_id)))
    return MCPInvocation(
        decision=receipt.decision.value,
        handler_executed=receipt.handler_executed,
        blocked_reason=receipt.blocked_reason,
        evidence_record_id=receipt.evidence_record_id,
        result=receipt.result,
    )
