from __future__ import annotations

from typing import Final, Optional, Union
from urllib.parse import urlparse

from zeus_agent.live_gateway_adapter_runtime import LiveGatewayAdapterResult
from zeus_agent.live_mcp_adapter_runtime import LiveMcpAdapterResult
from zeus_agent.live_provider_adapter_runtime import LiveProviderAdapterResult
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationResult
from zeus_agent.security.credentials import CredentialScope, CredentialScopeUnsafeError, redact_secret_spans

LiveAdapterPlan = Union[LiveProviderAdapterResult, LiveGatewayAdapterResult, LiveMcpAdapterResult]

ADAPTER_KINDS: Final = frozenset(("provider", "gateway", "mcp"))
TRANSPORT_KINDS: Final = frozenset(("external_http", "remote_server"))
LOOPBACK_HOSTS: Final = frozenset(("localhost", "127.0.0.1", "::1", "0.0.0.0"))


def activation_reasons(
    activation: Optional[LiveTransportActivationResult],
    adapter_kind: str,
    adapter_plan_id: Optional[str],
) -> tuple[str, ...]:
    if activation is None:
        return ("transport_activation_required",)
    reasons = []
    if activation.decision != "activation_ready" or not activation.live_transport_authorized:
        reasons.append("transport_activation_not_ready")
    if activation.adapter_kind != adapter_kind:
        reasons.append("activation_adapter_kind_mismatch")
    if activation.adapter_plan_id != adapter_plan_id:
        reasons.append("activation_adapter_plan_mismatch")
    if activation.live_transport_enabled or activation.network_opened or activation.handler_executed:
        reasons.append("transport_activation_side_effect_detected")
    if activation.credential_material_accessed or activation.raw_secret_returned:
        reasons.append("transport_activation_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def adapter_plan_id_and_reasons(adapter_kind: str, adapter_plan: LiveAdapterPlan) -> tuple[Optional[str], tuple[str, ...]]:
    if adapter_kind == "provider" and isinstance(adapter_plan, LiveProviderAdapterResult):
        return adapter_plan.adapter_plan_id, _provider_reasons(adapter_plan)
    if adapter_kind == "gateway" and isinstance(adapter_plan, LiveGatewayAdapterResult):
        return adapter_plan.adapter_plan_id, _gateway_reasons(adapter_plan)
    if adapter_kind == "mcp" and isinstance(adapter_plan, LiveMcpAdapterResult):
        return adapter_plan.adapter_plan_id, _mcp_reasons(adapter_plan)
    return getattr(adapter_plan, "adapter_plan_id", None), ("adapter_plan_kind_mismatch",)


def target_reasons(
    adapter_kind: str,
    transport_kind: str,
    remote_target: Optional[str],
    target_identity: Optional[str],
    allowed_remote_targets: tuple[str, ...],
    adapter_plan: LiveAdapterPlan,
) -> tuple[str, ...]:
    reasons = []
    if remote_target is None:
        reasons.append("remote_target_required")
    elif target_identity is None:
        reasons.append("remote_target_identity_required")
    elif target_identity.lower() in LOOPBACK_HOSTS:
        reasons.append("remote_target_must_not_be_loopback")
    if not allowed_remote_targets:
        reasons.append("remote_target_allowlist_required")
    if not allowlisted(remote_target, target_identity, allowed_remote_targets):
        reasons.append("remote_target_not_allowlisted")
    if not _target_matches_plan(adapter_kind, target_identity, remote_target, adapter_plan):
        reasons.append("remote_target_adapter_plan_mismatch")
    if adapter_kind in {"provider", "gateway"} and transport_kind != "external_http":
        reasons.append("{0}_external_http_transport_required".format(adapter_kind))
    if adapter_kind == "mcp" and transport_kind != "remote_server":
        reasons.append("mcp_remote_server_transport_required")
    return tuple(dict.fromkeys(reasons))


def credential_scope(value: str) -> tuple[Optional[str], tuple[str, ...]]:
    try:
        return CredentialScope.parse(value).label, ()
    except CredentialScopeUnsafeError:
        return None, ("credential_scope_secret_like",)
    except ValueError:
        return None, ("credential_scope_invalid",)


def binding_reasons(binding_ref: Optional[str], scope: Optional[str], target_identity: Optional[str]) -> tuple[str, ...]:
    if binding_ref is None:
        return ("credential_binding_ref_required",)
    if not binding_bound(binding_ref, scope, target_identity):
        return ("credential_binding_not_endpoint_bound",)
    return ()


def binding_bound(binding_ref: Optional[str], scope: Optional[str], target_identity: Optional[str]) -> bool:
    return bool(binding_ref and scope and target_identity and scope in binding_ref and target_identity in binding_ref)


def safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def safe_allowed_targets(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(target for target in (safe_optional(value) for value in values) if target is not None)


def safe_refs(*refs: str) -> tuple[Optional[str], ...]:
    return tuple(safe_optional(ref) for ref in refs)


def ref_reasons(refs: tuple[Optional[str], ...]) -> tuple[str, ...]:
    labels = ("policy_ref", "audit_ref", "redaction_ref", "teardown_ref", "production_review_ref")
    return tuple("{0}_required".format(label) for label, ref in zip(labels, refs) if ref is None)


def target_identity(adapter_kind: str, remote_target: str) -> Optional[str]:
    if adapter_kind == "gateway":
        return remote_target
    parsed = urlparse(remote_target)
    host = parsed.hostname if parsed.hostname is not None else remote_target
    return host.strip() or None


def allowlisted(remote_target: Optional[str], identity: Optional[str], allowed: tuple[str, ...]) -> bool:
    return bool(remote_target and (remote_target in allowed or (identity is not None and identity in allowed)))


def _provider_reasons(adapter_plan: LiveProviderAdapterResult) -> tuple[str, ...]:
    reasons = [] if adapter_plan.decision == "planned" and adapter_plan.adapter_plan_ready else ["adapter_plan_not_ready"]
    if adapter_plan.provider_invoked or adapter_plan.network_opened or adapter_plan.live_transport_enabled:
        reasons.append("adapter_plan_side_effect_detected")
    if adapter_plan.credential_material_accessed or adapter_plan.raw_secret_returned:
        reasons.append("adapter_plan_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _gateway_reasons(adapter_plan: LiveGatewayAdapterResult) -> tuple[str, ...]:
    reasons = [] if adapter_plan.decision == "planned" and adapter_plan.adapter_plan_ready else ["adapter_plan_not_ready"]
    if adapter_plan.delivery_attempted or adapter_plan.external_delivery_opened or adapter_plan.network_opened:
        reasons.append("adapter_plan_side_effect_detected")
    if adapter_plan.credential_material_accessed or adapter_plan.raw_secret_returned:
        reasons.append("adapter_plan_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _mcp_reasons(adapter_plan: LiveMcpAdapterResult) -> tuple[str, ...]:
    reasons = [] if adapter_plan.decision == "planned" and adapter_plan.adapter_plan_ready else ["adapter_plan_not_ready"]
    if adapter_plan.server_started or adapter_plan.tool_invoked or adapter_plan.network_opened:
        reasons.append("adapter_plan_side_effect_detected")
    if adapter_plan.resources_enabled or adapter_plan.prompts_enabled:
        reasons.append("adapter_plan_side_effect_detected")
    if adapter_plan.credential_material_accessed or adapter_plan.raw_secret_returned:
        reasons.append("adapter_plan_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _target_matches_plan(
    adapter_kind: str,
    target_identity_value: Optional[str],
    remote_target: Optional[str],
    adapter_plan: LiveAdapterPlan,
) -> bool:
    if adapter_kind == "provider" and isinstance(adapter_plan, LiveProviderAdapterResult):
        return target_identity_value == adapter_plan.endpoint_host
    if adapter_kind == "mcp" and isinstance(adapter_plan, LiveMcpAdapterResult):
        return target_identity_value == adapter_plan.endpoint_host
    if adapter_kind == "gateway" and isinstance(adapter_plan, LiveGatewayAdapterResult):
        return remote_target == adapter_plan.target
    return False
