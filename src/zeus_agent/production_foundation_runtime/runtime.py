from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.approval_cockpit_runtime import ApprovalCockpitRuntime
from zeus_agent.capability_runtime import SandboxPolicy
from zeus_agent.credential_readiness_runtime import CredentialReadinessRuntime
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.secret_resolver_runtime import SecretResolverPlanRuntime
from zeus_agent.security.credentials import redact_secret_spans
from zeus_agent.security_cockpit_runtime import SecurityCockpitRuntime

ProductionFoundationDecision = Literal["report", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
_TARGET_VERSION: Final = "v1.0.0-rc.1"
_OBJECTIVE_CONTRACT_ID: Final = "zeus.v1.0.0-rc.1.production_foundation"
_NOW: Final = datetime(2026, 6, 6, 0, 0, tzinfo=timezone.utc)
_EXPIRES_AT: Final = datetime(2026, 6, 7, 0, 0, tzinfo=timezone.utc)
_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "password=",
    "password:",
    "secret:",
    "token=",
    "token:",
    "api_key:",
    "apikey:",
    "private_key",
    "private-key",
    "-----begin",
)
_REQUIRED_CONTROLS: Final[tuple[str, ...]] = (
    "identity_principal",
    "auth_scope",
    "approval_receipt",
    "runtime_lease",
    "credential_binding",
    "secret_resolver",
    "audit_persistence",
    "sandbox_policy",
    "rollback_path",
    "independent_review",
)


class ProductionFoundationContract(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ProductionFoundationDecision
    target_version: str
    release_stage: Literal["production_foundation"]
    objective_contract_id: str
    profile: Literal["production_foundation"]
    blocked_reasons: tuple[str, ...] = ()
    required_controls: tuple[str, ...]
    operator_note: Optional[str] = None
    production_foundation_ready: bool
    production_ready: bool = False
    identity_runtime_available: bool = True
    auth_runtime_available: bool = True
    approval_runtime_available: bool = True
    runtime_lease_available: bool = True
    credential_binding_runtime_available: bool = True
    secret_resolver_runtime_available: bool = True
    audit_runtime_available: bool = True
    sandbox_policy_available: bool = True
    approval_receipt_required: bool = True
    credential_binding_required: bool = True
    runtime_lease_required: bool = True
    human_approval_required_for_live: bool = True
    rollback_required: bool = True
    independent_review_required: bool = True
    credential_bindings_ready: bool = False
    security_cockpit: dict[str, JsonValue]
    approval_cockpit: dict[str, JsonValue]
    credential_readiness: dict[str, JsonValue]
    secret_resolver: dict[str, JsonValue]
    runtime_lease: dict[str, JsonValue]
    sandbox_policy: dict[str, JsonValue]
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    authority_widened: bool = False
    live_production_claimed: bool = False
    workflow_self_modification: bool = False
    memory_auto_promotion: bool = False
    ontology_auto_promotion: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> ProductionFoundationContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = not any(marker in serialized for marker in _SECRET_MARKERS)
        return self.model_copy(update={"no_secret_echo": safe})


def build_production_foundation_contract(
    *,
    home: Path,
    include_credentials: bool = False,
    operator_note: Optional[str] = None,
) -> ProductionFoundationContract:
    blocked_reasons = _blocked_reasons(operator_note=operator_note)
    clean_operator_note = _operator_note(operator_note=operator_note, blocked_reasons=blocked_reasons)
    security = _public_payload(
        SecurityCockpitRuntime(home=home).build(include_credentials=include_credentials).to_payload(),
    )
    approval = _public_payload(ApprovalCockpitRuntime().build(approval_id="provider-live").to_payload())
    credential_readiness = _public_payload(CredentialReadinessRuntime(home).build().to_payload())
    secret_resolver = _public_payload(SecretResolverPlanRuntime(home).plan(
        surface_kind="provider",
        surface_id="provider.external.openai",
        credential_scope="external.openai.readonly",
        expected_endpoint="api.openai.com",
    ).to_payload())
    lease = _production_foundation_lease().model_dump(mode="json")
    sandbox = _sandbox_policy_payload(home=home)
    ready = not blocked_reasons and _controls_available(
        security=security,
        approval=approval,
        credential_readiness=credential_readiness,
        secret_resolver=secret_resolver,
        runtime_lease=lease,
        sandbox_policy=sandbox,
    )
    result = ProductionFoundationContract(
        decision="blocked" if blocked_reasons else "report",
        target_version=_TARGET_VERSION,
        release_stage="production_foundation",
        objective_contract_id=_OBJECTIVE_CONTRACT_ID,
        profile="production_foundation",
        blocked_reasons=blocked_reasons,
        required_controls=_REQUIRED_CONTROLS,
        operator_note=clean_operator_note,
        production_foundation_ready=ready,
        production_ready=False,
        credential_bindings_ready=_credential_bindings_ready(
            credential_readiness=credential_readiness,
            secret_resolver=secret_resolver,
        ),
        security_cockpit=security,
        approval_cockpit=approval,
        credential_readiness=credential_readiness,
        secret_resolver=secret_resolver,
        runtime_lease=lease,
        sandbox_policy=sandbox,
        network_opened=False,
        handler_executed=False,
        external_delivery_opened=False,
        credential_material_accessed=False,
        authority_widened=False,
        live_production_claimed=False,
        workflow_self_modification=False,
        memory_auto_promotion=False,
        ontology_auto_promotion=False,
    )
    return result.with_secret_scan()


def _production_foundation_lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="rc1.lease.production.foundation",
        objective_id="rc1.objective.production.foundation",
        principal_id="rc1.principal.operator",
        run_id="rc1.run.production.foundation",
        allowed_capabilities=(
            "provider.external.generate",
            "mcp.server.call",
            "gateway.dispatch.plan",
            "terminal.run",
            "sandbox.remote.execute",
            "audit.write",
        ),
        credential_scopes=(
            "external.openai.readonly",
            "external.mcp.readonly",
            "external.gateway.readonly",
        ),
        network_hosts=(
            "api.openai.com",
            "mcp.local",
            "gateway.local",
        ),
        budget_limit=10_000,
        evidence_target="mneme.rc1.production.foundation",
        live_transport_allowed=False,
        issued_at=_NOW,
        expires_at=_EXPIRES_AT,
    )


def _sandbox_policy_payload(*, home: Path) -> dict[str, JsonValue]:
    policy = SandboxPolicy()
    network_decision = policy.decide_command("curl https://example.com", home)
    destructive_decision = policy.decide_command("rm -rf .", home)
    read_decision = policy.decide_command("pwd", home)
    return {
        "decision": "report",
        "default_network_egress": "deny",
        "network_command_decision": network_decision.decision,
        "network_command_reason": network_decision.reason,
        "destructive_command_decision": destructive_decision.decision,
        "destructive_command_reason": destructive_decision.reason,
        "read_command_decision": read_decision.decision,
        "allowed_commands": list(policy.allowed_commands),
        "network_opened": False,
        "handler_executed": False,
        "external_delivery_opened": False,
        "credential_material_accessed": False,
        "live_production_claimed": False,
    }


def _controls_available(
    *,
    security: dict[str, JsonValue],
    approval: dict[str, JsonValue],
    credential_readiness: dict[str, JsonValue],
    secret_resolver: dict[str, JsonValue],
    runtime_lease: dict[str, JsonValue],
    sandbox_policy: dict[str, JsonValue],
) -> bool:
    return (
        security["decision"] == "report"
        and approval["decision"] == "report"
        and credential_readiness["decision"] == "report"
        and credential_readiness["ready_for_live_transport"] is True
        and secret_resolver["decision"] == "planned"
        and not secret_resolver["blocked_reasons"]
        and secret_resolver["endpoint_binding_valid"] is True
        and secret_resolver["material_access_allowed"] is False
        and runtime_lease["live_transport_allowed"] is False
        and sandbox_policy["network_command_decision"] == "blocked"
        and sandbox_policy["destructive_command_decision"] == "blocked"
    )


def _credential_bindings_ready(
    *,
    credential_readiness: dict[str, JsonValue],
    secret_resolver: dict[str, JsonValue],
) -> bool:
    return (
        credential_readiness["ready_for_live_transport"] is True
        and secret_resolver["decision"] == "planned"
        and secret_resolver["endpoint_binding_valid"] is True
    )


def _blocked_reasons(*, operator_note: Optional[str]) -> tuple[str, ...]:
    if operator_note is None:
        return ()
    if _has_secret_marker(operator_note):
        return ("raw_secret_marker_detected",)
    return ()


def _operator_note(*, operator_note: Optional[str], blocked_reasons: tuple[str, ...]) -> Optional[str]:
    if operator_note is None:
        return None
    if "raw_secret_marker_detected" in blocked_reasons:
        return "[redacted-secret]"
    clean = redact_secret_spans(operator_note.strip())
    if clean == "":
        return None
    return clean


def _has_secret_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)


def _public_payload(value: JsonValue) -> JsonValue:
    if isinstance(value, dict):
        return {key: _public_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_public_payload(item) for item in value]
    if isinstance(value, str):
        return value.replace("sk-...redacted", "[redacted-secret]")
    return value
