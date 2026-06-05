from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_remote_transport_policy_runtime.rules import (
    ADAPTER_KINDS,
    TRANSPORT_KINDS,
    LiveAdapterPlan,
    activation_reasons,
    adapter_plan_id_and_reasons,
    allowlisted,
    binding_bound,
    binding_reasons,
    credential_scope as parse_credential_scope,
    ref_reasons,
    safe_allowed_targets,
    safe_optional,
    safe_refs,
    target_identity,
    target_reasons,
)
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationResult

LiveRemotePolicyDecision = Literal["policy_ready", "blocked"]
LiveRemoteAdapterKind = Literal["provider", "gateway", "mcp"]
RemoteTransportKind = Literal["external_http", "remote_server"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-wave",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "token=sk",
    "password=",
    "secret=",
    "private_key",
    "private-key",
    "-----begin",
)


class LiveRemoteTransportPolicyResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveRemotePolicyDecision
    policy_id: Optional[str]
    activation_id: Optional[str]
    adapter_plan_id: Optional[str]
    adapter_kind: Optional[LiveRemoteAdapterKind]
    transport_kind: Optional[RemoteTransportKind]
    remote_target: Optional[str]
    remote_target_identity: Optional[str]
    credential_scope: Optional[str]
    credential_binding_ref: Optional[str]
    policy_ref: Optional[str]
    audit_ref: Optional[str]
    redaction_ref: Optional[str]
    teardown_ref: Optional[str]
    production_review_ref: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    activation_bound: bool = False
    adapter_plan_bound: bool = False
    remote_target_allowlisted: bool = False
    credential_scope_bound: bool = False
    credential_binding_bound: bool = False
    audit_required: bool = False
    redaction_required: bool = False
    teardown_required: bool = False
    production_review_required: bool = False
    remote_transport_requested: bool = False
    remote_transport_policy_ready: bool = False
    live_transport_authorized: bool = False
    live_transport_enabled: bool = False
    execution_allowed: bool = False
    authority_granted: bool = False
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    server_started: bool = False
    resources_enabled: bool = False
    prompts_enabled: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveRemoteTransportPolicyRuntime:
    def plan(
        self,
        *,
        activation: Optional[LiveTransportActivationResult],
        adapter_kind: str,
        adapter_plan: LiveAdapterPlan,
        transport_kind: str,
        remote_target: str,
        allowed_remote_targets: tuple[str, ...],
        credential_scope: str,
        credential_binding_ref: str,
        policy_ref: str,
        audit_ref: str,
        redaction_ref: str,
        teardown_ref: str,
        production_review_ref: str,
        resources_requested: bool = False,
        prompts_requested: bool = False,
    ) -> LiveRemoteTransportPolicyResult:
        safe_kind = adapter_kind.strip()
        safe_transport_kind = transport_kind.strip()
        safe_target = safe_optional(remote_target)
        identity = None if safe_target is None else target_identity(safe_kind, safe_target)
        safe_allowed = tuple(safe_allowed_targets(allowed_remote_targets))
        safe_scope, scope_reasons = parse_credential_scope(credential_scope)
        safe_binding = safe_optional(credential_binding_ref)
        refs = safe_refs(policy_ref, audit_ref, redaction_ref, teardown_ref, production_review_ref)
        adapter_plan_id, adapter_reasons = adapter_plan_id_and_reasons(safe_kind, adapter_plan)
        reasons = list(activation_reasons(activation, safe_kind, adapter_plan_id))
        reasons.extend(adapter_reasons)
        reasons.extend(scope_reasons)
        reasons.extend(target_reasons(safe_kind, safe_transport_kind, safe_target, identity, safe_allowed, adapter_plan))
        reasons.extend(binding_reasons(safe_binding, safe_scope, identity))
        reasons.extend(ref_reasons(refs))
        if resources_requested:
            reasons.append("mcp_resources_require_separate_policy")
        if prompts_requested:
            reasons.append("mcp_prompts_require_separate_policy")
        if safe_kind not in ADAPTER_KINDS:
            reasons.append("unsupported_adapter_kind")
        if safe_transport_kind not in TRANSPORT_KINDS:
            reasons.append("unsupported_remote_transport_kind")
        ready = not reasons
        return _result(
            decision="policy_ready" if ready else "blocked",
            activation=activation,
            adapter_kind=safe_kind,
            adapter_plan_id=adapter_plan_id,
            transport_kind=safe_transport_kind,
            remote_target=safe_target,
            remote_target_identity=identity,
            credential_scope=safe_scope,
            credential_binding_ref=safe_binding,
            safe_refs=refs,
            blocked_reasons=tuple(dict.fromkeys(reasons)),
            activation_bound=ready,
            adapter_plan_bound=ready,
            remote_target_allowlisted=allowlisted(safe_target, identity, safe_allowed),
            credential_scope_bound=safe_scope is not None,
            credential_binding_bound=binding_bound(safe_binding, safe_scope, identity),
            remote_transport_policy_ready=ready,
        )


def _policy_id(adapter_kind: str, adapter_plan_id: Optional[str], remote_target: Optional[str], policy_ref: Optional[str]) -> str:
    payload = {
        "adapter_kind": adapter_kind,
        "adapter_plan_id": adapter_plan_id,
        "policy_ref": policy_ref,
        "remote_target": remote_target,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-remote-policy-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveRemotePolicyDecision,
    activation: Optional[LiveTransportActivationResult],
    adapter_kind: str,
    adapter_plan_id: Optional[str],
    transport_kind: str,
    remote_target: Optional[str],
    remote_target_identity: Optional[str],
    credential_scope: Optional[str],
    credential_binding_ref: Optional[str],
    safe_refs: tuple[Optional[str], ...],
    blocked_reasons: tuple[str, ...],
    activation_bound: bool,
    adapter_plan_bound: bool,
    remote_target_allowlisted: bool,
    credential_scope_bound: bool,
    credential_binding_bound: bool,
    remote_transport_policy_ready: bool,
) -> LiveRemoteTransportPolicyResult:
    kind: Optional[LiveRemoteAdapterKind] = adapter_kind if adapter_kind in ADAPTER_KINDS else None
    transport: Optional[RemoteTransportKind] = transport_kind if transport_kind in TRANSPORT_KINDS else None
    result = LiveRemoteTransportPolicyResult(
        decision=decision,
        policy_id=None if decision == "blocked" else _policy_id(adapter_kind, adapter_plan_id, remote_target, safe_refs[0]),
        activation_id=None if activation is None else activation.activation_id,
        adapter_plan_id=adapter_plan_id,
        adapter_kind=kind,
        transport_kind=transport,
        remote_target=remote_target,
        remote_target_identity=remote_target_identity,
        credential_scope=credential_scope,
        credential_binding_ref=credential_binding_ref,
        policy_ref=safe_refs[0],
        audit_ref=safe_refs[1],
        redaction_ref=safe_refs[2],
        teardown_ref=safe_refs[3],
        production_review_ref=safe_refs[4],
        blocked_reasons=blocked_reasons,
        activation_bound=activation_bound,
        adapter_plan_bound=adapter_plan_bound,
        remote_target_allowlisted=remote_target_allowlisted,
        credential_scope_bound=credential_scope_bound,
        credential_binding_bound=credential_binding_bound,
        audit_required=safe_refs[1] is not None,
        redaction_required=safe_refs[2] is not None,
        teardown_required=safe_refs[3] is not None,
        production_review_required=safe_refs[4] is not None,
        remote_transport_requested=transport is not None,
        remote_transport_policy_ready=remote_transport_policy_ready,
        live_transport_authorized=activation is not None and activation.live_transport_authorized,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _no_secret_echo(result: LiveRemoteTransportPolicyResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
