from __future__ import annotations

from typing import Optional

from zeus_agent.security.credentials import redact_secret_spans
from zeus_agent.zeus_identity_activation_runtime.models import REQUIRED_ACTIVATION_REQUIREMENTS
from zeus_agent.zeus_identity_activation_runtime.models import SECRET_MARKERS
from zeus_agent.zeus_identity_activation_runtime.models import ZeusIdentityActivationContract
from zeus_agent.zeus_identity_activation_runtime.models import ZeusIdentityActivationDecision
from zeus_agent.zeus_identity_activation_runtime.models import ZeusIdentityActivationScenario


def build_zeus_identity_activation_contract(
    *,
    scenario: str = "identity-status",
    message: Optional[str] = None,
    objective_id: Optional[str] = None,
    lease_id: Optional[str] = None,
    approval_id: Optional[str] = None,
    credential_binding_ref: Optional[str] = None,
    sandbox_policy_ref: Optional[str] = None,
    audit_receipt_ref: Optional[str] = None,
    operator_note: Optional[str] = None,
) -> ZeusIdentityActivationContract:
    safe_scenario = _scenario(scenario)
    if safe_scenario is None:
        return _contract(decision="blocked", scenario="identity-status", blocked_reasons=("unsupported_scenario",))
    if _has_secret_marker(operator_note) or _has_secret_marker(message):
        return _contract(
            decision="blocked",
            scenario=safe_scenario,
            blocked_reasons=("raw_secret_marker_detected",),
            raw_secret_marker_detected=True,
        )
    if safe_scenario == "identity-status":
        return _contract(decision="report", scenario=safe_scenario, zeus_identity_ready=True)
    if safe_scenario == "korean-call-smoke":
        return _call_smoke(message=message)
    if safe_scenario == "activation-status":
        return _activation_status()
    return _activation_check(
        objective_id=objective_id,
        lease_id=lease_id,
        approval_id=approval_id,
        credential_binding_ref=credential_binding_ref,
        sandbox_policy_ref=sandbox_policy_ref,
        audit_receipt_ref=audit_receipt_ref,
    )


def _call_smoke(*, message: Optional[str]) -> ZeusIdentityActivationContract:
    response = _call_response(message)
    if response is None:
        return _contract(
            decision="blocked",
            scenario="korean-call-smoke",
            blocked_reasons=("zeus_call_name_required",),
        )
    return _contract(
        decision="report",
        scenario="korean-call-smoke",
        call_response=response,
        zeus_identity_ready=True,
    )


def _activation_status() -> ZeusIdentityActivationContract:
    return _contract(
        decision="report",
        scenario="activation-status",
        zeus_identity_ready=True,
    )


def _activation_check(
    *,
    objective_id: Optional[str],
    lease_id: Optional[str],
    approval_id: Optional[str],
    credential_binding_ref: Optional[str],
    sandbox_policy_ref: Optional[str],
    audit_receipt_ref: Optional[str],
) -> ZeusIdentityActivationContract:
    bindings = {
        "objective": _safe_ref(objective_id) is not None,
        "runtime_lease": _safe_ref(lease_id) is not None,
        "human_approval": _safe_ref(approval_id) is not None,
        "credential_binding": _safe_ref(credential_binding_ref) is not None,
        "sandbox_policy": _safe_ref(sandbox_policy_ref) is not None,
        "audit_receipt": _safe_ref(audit_receipt_ref) is not None,
    }
    missing = tuple(requirement for requirement in REQUIRED_ACTIVATION_REQUIREMENTS if not bindings[requirement])
    satisfied = tuple(requirement for requirement in REQUIRED_ACTIVATION_REQUIREMENTS if bindings[requirement])
    ready = len(missing) == 0
    reasons = tuple(f"{requirement}_required" for requirement in missing)
    return _contract(
        decision="report" if ready else "blocked",
        scenario="activation-check",
        blocked_reasons=reasons,
        zeus_identity_ready=True,
        live_activation_foundation_ready=ready,
        activation_contract_ready=ready,
        satisfied_activation_requirements=satisfied,
        missing_activation_requirements=missing,
        objective_bound=bindings["objective"],
        activation_lease_bound=bindings["runtime_lease"],
        approval_receipt_bound=bindings["human_approval"],
        credential_binding_bound=bindings["credential_binding"],
        sandbox_policy_bound=bindings["sandbox_policy"],
        audit_receipt_bound=bindings["audit_receipt"],
    )


def _contract(
    *,
    decision: ZeusIdentityActivationDecision,
    scenario: ZeusIdentityActivationScenario,
    blocked_reasons: tuple[str, ...] = (),
    call_response: Optional[str] = None,
    zeus_identity_ready: bool = False,
    live_activation_foundation_ready: bool = False,
    activation_contract_ready: bool = False,
    satisfied_activation_requirements: tuple[str, ...] = (),
    missing_activation_requirements: tuple[str, ...] = REQUIRED_ACTIVATION_REQUIREMENTS,
    objective_bound: bool = False,
    activation_lease_bound: bool = False,
    approval_receipt_bound: bool = False,
    credential_binding_bound: bool = False,
    sandbox_policy_bound: bool = False,
    audit_receipt_bound: bool = False,
    raw_secret_marker_detected: bool = False,
) -> ZeusIdentityActivationContract:
    result = ZeusIdentityActivationContract(
        decision=decision,
        scenario=scenario,
        blocked_reasons=blocked_reasons,
        call_response=call_response,
        zeus_identity_ready=zeus_identity_ready,
        live_activation_foundation_ready=live_activation_foundation_ready,
        activation_contract_ready=activation_contract_ready,
        satisfied_activation_requirements=satisfied_activation_requirements,
        missing_activation_requirements=missing_activation_requirements,
        objective_bound=objective_bound,
        activation_lease_bound=activation_lease_bound,
        approval_receipt_bound=approval_receipt_bound,
        credential_binding_bound=credential_binding_bound,
        sandbox_policy_bound=sandbox_policy_bound,
        audit_receipt_bound=audit_receipt_bound,
        raw_secret_marker_detected=raw_secret_marker_detected,
    )
    return result.with_secret_scan()


def _scenario(value: str) -> Optional[ZeusIdentityActivationScenario]:
    candidate = value.strip()
    if candidate == "identity-status":
        return "identity-status"
    if candidate == "korean-call-smoke":
        return "korean-call-smoke"
    if candidate == "activation-status":
        return "activation-status"
    if candidate == "activation-check":
        return "activation-check"
    return None


def _call_response(message: Optional[str]) -> Optional[str]:
    if message is None:
        return None
    normalized = redact_secret_spans(message.strip()).casefold()
    if normalized in {"제우스", "제우스야"}:
        return "네, 제우스입니다."
    if normalized in {"zeus", "zeus.", "hey zeus", "hello zeus"}:
        return "Zeus is here."
    return None


def _safe_ref(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _has_secret_marker(value: Optional[str]) -> bool:
    if value is None:
        return False
    lowered = value.lower()
    return any(marker in lowered for marker in SECRET_MARKERS)
