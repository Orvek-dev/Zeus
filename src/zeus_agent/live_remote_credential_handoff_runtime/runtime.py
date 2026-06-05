from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialResult
from zeus_agent.security.credentials import redact_secret_spans

LiveRemoteCredentialHandoffDecision = Literal["handoff_ready", "blocked"]
LiveRemoteAdapterKind = Literal["provider", "gateway", "mcp"]
RemoteAuthScheme = Literal["bearer", "api_key"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_AUTH_SCHEMES: Final = frozenset(("bearer", "api_key"))
_HEADER_BY_SCHEME: Final = {"bearer": "Authorization", "api_key": "X-API-Key"}
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


class LiveRemoteCredentialHandoffResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveRemoteCredentialHandoffDecision
    handoff_id: Optional[str]
    policy_id: Optional[str]
    material_proof_id: Optional[str]
    adapter_kind: Optional[LiveRemoteAdapterKind]
    remote_target_identity: Optional[str]
    credential_scope: Optional[str]
    secret_ref: Optional[str]
    handoff_ref: Optional[str]
    auth_scheme: Optional[RemoteAuthScheme]
    header_name: Optional[str]
    header_value_ref: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    policy_bound: bool = False
    secret_material_bound: bool = False
    endpoint_binding_verified: bool = False
    header_binding_planned: bool = False
    credential_handoff_ready: bool = False
    credential_material_accessed: bool = False
    material_released: bool = False
    raw_secret_returned: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    live_transport_enabled: bool = False
    execution_allowed: bool = False
    authority_granted: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveRemoteCredentialHandoffRuntime:
    def prepare(
        self,
        *,
        policy: Optional[LiveRemoteTransportPolicyResult],
        secret_material: Optional[LiveSecretMaterialResult],
        handoff_ref: str,
        auth_scheme: str,
        header_name: str,
    ) -> LiveRemoteCredentialHandoffResult:
        safe_ref = _safe_optional(handoff_ref)
        safe_scheme = auth_scheme.strip()
        safe_header = _safe_header_name(header_name)
        reasons = list(_policy_reasons(policy))
        reasons.extend(_secret_material_reasons(secret_material))
        reasons.extend(_header_reasons(safe_scheme, safe_header))
        if safe_ref is None:
            reasons.append("handoff_ref_required")
        ready = not reasons
        return _result(
            decision="handoff_ready" if ready else "blocked",
            policy=policy,
            secret_material=secret_material,
            handoff_ref=safe_ref,
            auth_scheme=safe_scheme,
            header_name=safe_header,
            blocked_reasons=tuple(dict.fromkeys(reasons)),
            policy_bound=ready,
            secret_material_bound=ready,
            endpoint_binding_verified=ready,
            header_binding_planned=ready,
            credential_handoff_ready=ready,
        )


def _policy_reasons(policy: Optional[LiveRemoteTransportPolicyResult]) -> tuple[str, ...]:
    if policy is None:
        return ("remote_policy_required",)
    reasons = []
    if policy.decision != "policy_ready" or not policy.remote_transport_policy_ready:
        reasons.append("remote_policy_not_ready")
    if not policy.credential_binding_bound or not policy.remote_target_allowlisted:
        reasons.append("remote_policy_binding_not_ready")
    if policy.live_transport_enabled or policy.network_opened or policy.handler_executed:
        reasons.append("remote_policy_side_effect_detected")
    if policy.credential_material_accessed or policy.raw_secret_returned:
        reasons.append("remote_policy_secret_leak_detected")
    if policy.live_production_claimed or not policy.no_secret_echo:
        reasons.append("remote_policy_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _secret_material_reasons(secret_material: Optional[LiveSecretMaterialResult]) -> tuple[str, ...]:
    if secret_material is None:
        return ("secret_material_required",)
    reasons = []
    if secret_material.decision != "available" or not secret_material.material_available:
        reasons.append("secret_material_not_available")
    if not secret_material.material_proof_id:
        reasons.append("secret_material_proof_required")
    if secret_material.material_released or secret_material.raw_secret_returned:
        reasons.append("secret_material_leak_detected")
    if secret_material.network_opened or secret_material.external_delivery_opened:
        reasons.append("secret_material_side_effect_detected")
    if secret_material.live_transport_enabled or secret_material.live_production_claimed:
        reasons.append("secret_material_side_effect_detected")
    if not secret_material.no_secret_echo:
        reasons.append("secret_material_secret_echo_detected")
    return tuple(dict.fromkeys(reasons))


def _header_reasons(auth_scheme: str, header_name: str) -> tuple[str, ...]:
    reasons = []
    if auth_scheme not in _AUTH_SCHEMES:
        reasons.append("unsupported_auth_scheme")
    expected = _HEADER_BY_SCHEME.get(auth_scheme)
    if expected is None or header_name != expected:
        reasons.append("credential_header_mismatch")
    if header_name == "":
        reasons.append("credential_header_required")
    return tuple(dict.fromkeys(reasons))


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _safe_header_name(value: str) -> str:
    header = value.strip()
    if header in set(_HEADER_BY_SCHEME.values()):
        return header
    return redact_secret_spans(header)


def _header_value_ref(secret_material: Optional[LiveSecretMaterialResult]) -> Optional[str]:
    if secret_material is None or not secret_material.material_proof_id:
        return None
    return "secret-proof://{0}".format(secret_material.material_proof_id)


def _handoff_id(
    *,
    policy: Optional[LiveRemoteTransportPolicyResult],
    secret_material: Optional[LiveSecretMaterialResult],
    handoff_ref: Optional[str],
    auth_scheme: str,
    header_name: str,
) -> str:
    payload = {
        "auth_scheme": auth_scheme,
        "handoff_ref": handoff_ref,
        "header_name": header_name,
        "material_proof_id": None if secret_material is None else secret_material.material_proof_id,
        "policy_id": None if policy is None else policy.policy_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-credential-handoff-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveRemoteCredentialHandoffDecision,
    policy: Optional[LiveRemoteTransportPolicyResult],
    secret_material: Optional[LiveSecretMaterialResult],
    handoff_ref: Optional[str],
    auth_scheme: str,
    header_name: str,
    blocked_reasons: tuple[str, ...],
    policy_bound: bool,
    secret_material_bound: bool,
    endpoint_binding_verified: bool,
    header_binding_planned: bool,
    credential_handoff_ready: bool,
) -> LiveRemoteCredentialHandoffResult:
    scheme: Optional[RemoteAuthScheme] = auth_scheme if auth_scheme in _AUTH_SCHEMES else None
    result = LiveRemoteCredentialHandoffResult(
        decision=decision,
        handoff_id=None if decision == "blocked" else _handoff_id(
            policy=policy,
            secret_material=secret_material,
            handoff_ref=handoff_ref,
            auth_scheme=auth_scheme,
            header_name=header_name,
        ),
        policy_id=None if policy is None else policy.policy_id,
        material_proof_id=None if secret_material is None else secret_material.material_proof_id,
        adapter_kind=None if policy is None else policy.adapter_kind,
        remote_target_identity=None if policy is None else policy.remote_target_identity,
        credential_scope=None if policy is None else policy.credential_scope,
        secret_ref=None if secret_material is None else secret_material.secret_ref,
        handoff_ref=handoff_ref,
        auth_scheme=scheme,
        header_name=header_name if header_name else None,
        header_value_ref=_header_value_ref(secret_material) if decision == "handoff_ready" else None,
        blocked_reasons=blocked_reasons,
        policy_bound=policy_bound,
        secret_material_bound=secret_material_bound,
        endpoint_binding_verified=endpoint_binding_verified,
        header_binding_planned=header_binding_planned,
        credential_handoff_ready=credential_handoff_ready,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _no_secret_echo(result: LiveRemoteCredentialHandoffResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
