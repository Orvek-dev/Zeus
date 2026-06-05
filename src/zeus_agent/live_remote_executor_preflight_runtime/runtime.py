from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_remote_credential_handoff_runtime import LiveRemoteCredentialHandoffResult
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult
from zeus_agent.security.credentials import redact_secret_spans

LiveRemoteExecutorPreflightDecision = Literal["preflight_ready", "blocked"]
LiveRemoteAdapterKind = Literal["provider", "gateway", "mcp"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_ADAPTER_KINDS: Final = frozenset(("provider", "gateway", "mcp"))
_MAX_TIMEOUT_MS: Final = 60_000
_MAX_RETRY_ATTEMPTS: Final = 3
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


class LiveRemoteExecutorPreflightResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveRemoteExecutorPreflightDecision
    preflight_id: Optional[str]
    policy_id: Optional[str]
    handoff_id: Optional[str]
    adapter_kind: Optional[LiveRemoteAdapterKind]
    remote_target_identity: Optional[str]
    credential_scope: Optional[str]
    executor_ref: Optional[str]
    idempotency_key: Optional[str]
    teardown_ref: Optional[str]
    timeout_ms: int
    retry_attempts: int
    blocked_reasons: tuple[str, ...] = ()
    policy_bound: bool = False
    credential_handoff_bound: bool = False
    endpoint_binding_verified: bool = False
    idempotency_bound: bool = False
    timeout_retry_bound: bool = False
    teardown_bound: bool = False
    remote_executor_preflight_ready: bool = False
    credential_material_accessed: bool = False
    material_released: bool = False
    raw_secret_returned: bool = False
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    live_transport_enabled: bool = False
    execution_allowed: bool = False
    authority_granted: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveRemoteExecutorPreflightRuntime:
    def plan(
        self,
        *,
        policy: Optional[LiveRemoteTransportPolicyResult],
        handoff: Optional[LiveRemoteCredentialHandoffResult],
        executor_kind: str,
        executor_ref: str,
        idempotency_key: str,
        teardown_ref: str,
        timeout_ms: int,
        retry_attempts: int,
    ) -> LiveRemoteExecutorPreflightResult:
        safe_kind = executor_kind.strip()
        safe_executor_ref = _safe_optional(executor_ref)
        safe_idempotency = _safe_optional(idempotency_key)
        safe_teardown = _safe_optional(teardown_ref)
        reasons = list(_policy_reasons(policy, safe_kind, safe_teardown))
        reasons.extend(_handoff_reasons(handoff, policy))
        reasons.extend(_executor_reasons(safe_kind, safe_executor_ref, safe_idempotency, timeout_ms, retry_attempts))
        if safe_teardown is None:
            reasons.append("teardown_ref_required")
        ready = not reasons
        return _result(
            decision="preflight_ready" if ready else "blocked",
            policy=policy,
            handoff=handoff,
            executor_kind=safe_kind,
            executor_ref=safe_executor_ref,
            idempotency_key=safe_idempotency,
            teardown_ref=safe_teardown,
            timeout_ms=timeout_ms,
            retry_attempts=retry_attempts,
            blocked_reasons=tuple(dict.fromkeys(reasons)),
            policy_bound=ready,
            credential_handoff_bound=ready,
            endpoint_binding_verified=ready,
            idempotency_bound=safe_idempotency is not None,
            timeout_retry_bound=_timeout_retry_bound(timeout_ms, retry_attempts),
            teardown_bound=ready,
            remote_executor_preflight_ready=ready,
        )


def _policy_reasons(
    policy: Optional[LiveRemoteTransportPolicyResult],
    executor_kind: str,
    teardown_ref: Optional[str],
) -> tuple[str, ...]:
    if policy is None:
        return ("remote_policy_required",)
    reasons = []
    if policy.decision != "policy_ready" or not policy.remote_transport_policy_ready:
        reasons.append("remote_policy_not_ready")
    if policy.adapter_kind != executor_kind:
        reasons.append("executor_kind_policy_mismatch")
    if policy.teardown_ref != teardown_ref:
        reasons.append("teardown_ref_policy_mismatch")
    if policy.network_opened or policy.handler_executed or policy.live_transport_enabled:
        reasons.append("remote_policy_side_effect_detected")
    if policy.credential_material_accessed or policy.raw_secret_returned or not policy.no_secret_echo:
        reasons.append("remote_policy_secret_leak_detected")
    if policy.live_production_claimed:
        reasons.append("remote_policy_production_claim_detected")
    return tuple(dict.fromkeys(reasons))


def _handoff_reasons(
    handoff: Optional[LiveRemoteCredentialHandoffResult],
    policy: Optional[LiveRemoteTransportPolicyResult],
) -> tuple[str, ...]:
    if handoff is None:
        return ("credential_handoff_required",)
    reasons = []
    if handoff.decision != "handoff_ready" or not handoff.credential_handoff_ready:
        reasons.append("credential_handoff_not_ready")
    if policy is not None and handoff.policy_id != policy.policy_id:
        reasons.append("credential_handoff_policy_mismatch")
    if handoff.material_released or handoff.raw_secret_returned or not handoff.no_secret_echo:
        reasons.append("credential_handoff_secret_leak_detected")
    if handoff.network_opened or handoff.external_delivery_opened or handoff.live_transport_enabled:
        reasons.append("credential_handoff_side_effect_detected")
    if handoff.live_production_claimed:
        reasons.append("credential_handoff_production_claim_detected")
    return tuple(dict.fromkeys(reasons))


def _executor_reasons(
    executor_kind: str,
    executor_ref: Optional[str],
    idempotency_key: Optional[str],
    timeout_ms: int,
    retry_attempts: int,
) -> tuple[str, ...]:
    reasons = []
    if executor_kind not in _ADAPTER_KINDS:
        reasons.append("unsupported_executor_kind")
    if executor_ref is None:
        reasons.append("executor_ref_required")
    if idempotency_key is None:
        reasons.append("idempotency_key_required")
    if not _timeout_retry_bound(timeout_ms, retry_attempts):
        reasons.append("timeout_retry_out_of_bounds")
    return tuple(dict.fromkeys(reasons))


def _timeout_retry_bound(timeout_ms: int, retry_attempts: int) -> bool:
    return 0 < timeout_ms <= _MAX_TIMEOUT_MS and 0 <= retry_attempts <= _MAX_RETRY_ATTEMPTS


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _preflight_id(
    *,
    policy: Optional[LiveRemoteTransportPolicyResult],
    handoff: Optional[LiveRemoteCredentialHandoffResult],
    executor_ref: Optional[str],
    idempotency_key: Optional[str],
) -> str:
    payload = {
        "executor_ref": executor_ref,
        "handoff_id": None if handoff is None else handoff.handoff_id,
        "idempotency_key": idempotency_key,
        "policy_id": None if policy is None else policy.policy_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-remote-preflight-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveRemoteExecutorPreflightDecision,
    policy: Optional[LiveRemoteTransportPolicyResult],
    handoff: Optional[LiveRemoteCredentialHandoffResult],
    executor_kind: str,
    executor_ref: Optional[str],
    idempotency_key: Optional[str],
    teardown_ref: Optional[str],
    timeout_ms: int,
    retry_attempts: int,
    blocked_reasons: tuple[str, ...],
    policy_bound: bool,
    credential_handoff_bound: bool,
    endpoint_binding_verified: bool,
    idempotency_bound: bool,
    timeout_retry_bound: bool,
    teardown_bound: bool,
    remote_executor_preflight_ready: bool,
) -> LiveRemoteExecutorPreflightResult:
    kind: Optional[LiveRemoteAdapterKind] = executor_kind if executor_kind in _ADAPTER_KINDS else None
    result = LiveRemoteExecutorPreflightResult(
        decision=decision,
        preflight_id=None if decision == "blocked" else _preflight_id(
            policy=policy,
            handoff=handoff,
            executor_ref=executor_ref,
            idempotency_key=idempotency_key,
        ),
        policy_id=None if policy is None else policy.policy_id,
        handoff_id=None if handoff is None else handoff.handoff_id,
        adapter_kind=kind,
        remote_target_identity=None if policy is None else policy.remote_target_identity,
        credential_scope=None if policy is None else policy.credential_scope,
        executor_ref=executor_ref,
        idempotency_key=idempotency_key,
        teardown_ref=teardown_ref,
        timeout_ms=timeout_ms,
        retry_attempts=retry_attempts,
        blocked_reasons=blocked_reasons,
        policy_bound=policy_bound,
        credential_handoff_bound=credential_handoff_bound,
        endpoint_binding_verified=endpoint_binding_verified,
        idempotency_bound=idempotency_bound,
        timeout_retry_bound=timeout_retry_bound,
        teardown_bound=teardown_bound,
        remote_executor_preflight_ready=remote_executor_preflight_ready,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _no_secret_echo(result: LiveRemoteExecutorPreflightResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
