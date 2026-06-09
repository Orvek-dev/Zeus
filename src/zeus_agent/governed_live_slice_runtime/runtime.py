from __future__ import annotations

from typing import Optional

from zeus_agent.governed_live_slice_runtime.models import GovernedLiveSliceResult, GovernedLiveSurface
from zeus_agent.live_governance_runtime import (
    GovernedLiveDispatcher,
    GovernedLiveRequest,
    default_live_capability_registry,
    default_live_governance_trust_store,
)


def build_governed_live_slice(
    *,
    surface: GovernedLiveSurface = "provider",
    capability_id: str = "provider.local-smoke",
    scenario: str = "local-smoke",
    objective_run_id: Optional[str] = None,
    lease_ref: Optional[str] = None,
    approval_ref: Optional[str] = None,
    promotion_guard_ref: Optional[str] = None,
    broker_evidence_ref: Optional[str] = None,
    credential_scope: Optional[str] = None,
    sandbox_policy_ref: Optional[str] = None,
    audit_receipt_ref: Optional[str] = None,
    network_host: Optional[str] = None,
    raw_credential: Optional[str] = None,
) -> GovernedLiveSliceResult:
    missing = _missing_requirements(
        objective_run_id=objective_run_id,
        lease_ref=lease_ref,
        approval_ref=approval_ref,
        promotion_guard_ref=promotion_guard_ref,
        broker_evidence_ref=broker_evidence_ref,
        credential_scope=credential_scope,
        sandbox_policy_ref=sandbox_policy_ref,
        audit_receipt_ref=audit_receipt_ref,
    )
    request = GovernedLiveRequest(
        provider=_provider_for_surface(surface),
        capability_id=capability_id,
        scenario=scenario,
        lease_ref=lease_ref,
        approval_ref=approval_ref,
        promotion_guard_ref=promotion_guard_ref,
        broker_evidence_ref=broker_evidence_ref,
        credential_scope=credential_scope,
        network_host=network_host,
        raw_credential=raw_credential,
    )
    dispatcher = GovernedLiveDispatcher(
        capability_registry=default_live_capability_registry(),
        trust_store=default_live_governance_trust_store(),
    )
    governed = dispatcher.dispatch(request)
    blocked_reasons = tuple(dict.fromkeys((*governed.blocked_reasons, *_missing_reasons(missing))))
    decision = "allowed" if governed.decision == "allowed" and not missing else "blocked"
    return GovernedLiveSliceResult(
        decision=decision,
        surface=surface,
        capability_id=capability_id,
        scenario=scenario,
        blocked_reasons=() if decision == "allowed" else blocked_reasons,
        missing_requirements=missing,
        operator_next_steps=() if decision == "allowed" else _operator_next_steps(blocked_reasons, missing),
        trusted_loopback_live_smoke_available=governed.decision == "allowed",
        lease_bound=governed.lease_bound,
        approval_bound=governed.approval_bound,
        promotion_guard_bound=governed.promotion_guard_bound,
        broker_evidence_bound=governed.broker_evidence_bound,
        broker_decision=governed.broker_decision,
        broker_evidence_status=governed.broker_evidence_status,
        broker_evidence_type=governed.broker_evidence_type,
        no_secret_echo=governed.no_secret_echo,
        raw_secret_returned=governed.raw_secret_returned,
        network_opened=False,
        credential_material_accessed=False,
        external_delivery_opened=False,
        handler_executed=governed.handler_executed if decision == "allowed" else False,
        live_production_claimed=False,
        production_ready=False,
    )


def _provider_for_surface(surface: GovernedLiveSurface) -> str:
    if surface == "provider":
        return "provider"
    return surface.replace("_", "-")


def _missing_requirements(
    *,
    objective_run_id: Optional[str],
    lease_ref: Optional[str],
    approval_ref: Optional[str],
    promotion_guard_ref: Optional[str],
    broker_evidence_ref: Optional[str],
    credential_scope: Optional[str],
    sandbox_policy_ref: Optional[str],
    audit_receipt_ref: Optional[str],
) -> tuple[str, ...]:
    checks = (
        ("objective_run_id", objective_run_id),
        ("lease_ref", lease_ref),
        ("approval_ref", approval_ref),
        ("promotion_guard_ref", promotion_guard_ref),
        ("broker_evidence_ref", broker_evidence_ref),
        ("credential_scope", credential_scope),
        ("sandbox_policy_ref", sandbox_policy_ref),
        ("audit_receipt_ref", audit_receipt_ref),
    )
    return tuple(name for name, value in checks if value is None or value.strip() == "")


def _missing_reasons(missing: tuple[str, ...]) -> tuple[str, ...]:
    mapping = {
        "objective_run_id": "objective.missing_objective_run",
        "lease_ref": "lease.missing_lease",
        "approval_ref": "approval.missing_approval",
        "promotion_guard_ref": "promotion_guard.missing_promotion_guard",
        "broker_evidence_ref": "broker_evidence.missing_broker_evidence_ref",
        "credential_scope": "credential_scope.missing_credential_scope",
        "sandbox_policy_ref": "sandbox.missing_sandbox_policy",
        "audit_receipt_ref": "audit.missing_audit_receipt",
    }
    return tuple(mapping[item] for item in missing)


def _operator_next_steps(blocked_reasons: tuple[str, ...], missing: tuple[str, ...]) -> tuple[str, ...]:
    steps = []
    if "objective_run_id" in missing:
        steps.append("Start or select an ObjectiveRun so the live-capable action is tied to a goal.")
    if "lease_ref" in missing:
        steps.append("Create a runtime lease with scoped capability, budget, timeout, path, network, and credential bounds.")
    if "approval_ref" in missing:
        steps.append("Collect a human approval receipt for the requested live-capable capability.")
    if "credential_scope" in missing:
        steps.append("Use a credential scope or secret reference instead of raw credential material.")
    if "sandbox_policy_ref" in missing:
        steps.append("Attach a sandbox policy before any handler can produce side effects.")
    if "audit_receipt_ref" in missing:
        steps.append("Attach an audit receipt so the run has inspectable execution evidence.")
    if any("raw_secret" in reason for reason in blocked_reasons):
        steps.append("Remove raw credential text and retry with a scoped secret reference.")
    return tuple(dict.fromkeys(steps))
