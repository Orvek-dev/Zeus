from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_executor_release_runtime import LiveExecutorReleaseResult
from zeus_agent.live_provider_request_runtime import LiveProviderRequestResult
from zeus_agent.security.credentials import redact_secret_spans

LiveProviderAdapterDecision = Literal["planned", "blocked"]
ProviderTransportMode = Literal["dry_run", "live"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_TRANSPORT_MODES: Final = frozenset(("dry_run", "live"))
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


class LiveProviderAdapterResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveProviderAdapterDecision
    adapter_plan_id: Optional[str]
    release_id: Optional[str]
    request_envelope_id: Optional[str]
    provider_kind: Optional[str]
    model_id: Optional[str]
    endpoint_host: Optional[str]
    transport_mode: Optional[ProviderTransportMode]
    timeout_ms: int
    retry_attempts: int
    idempotency_key: str
    blocked_reasons: tuple[str, ...] = ()
    adapter_plan_ready: bool = False
    release_bound: bool = False
    provider_envelope_bound: bool = False
    live_transport_requested: bool = False
    provider_invoked: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    execution_allowed: bool = False
    authority_granted: bool = False
    live_transport_enabled: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveProviderAdapterRuntime:
    def plan(
        self,
        *,
        release: Optional[LiveExecutorReleaseResult],
        provider_envelope: LiveProviderRequestResult,
        transport_mode: str,
        timeout_ms: int,
        retry_attempts: int,
        idempotency_key: str,
    ) -> LiveProviderAdapterResult:
        safe_mode = transport_mode.strip()
        safe_idempotency_key = redact_secret_spans(idempotency_key.strip())
        reasons = list(_release_reasons(release=release, provider_envelope=provider_envelope))
        reasons.extend(_provider_envelope_reasons(provider_envelope))
        reasons.extend(_policy_reasons(safe_mode, timeout_ms, retry_attempts, safe_idempotency_key))
        if reasons:
            return _result(
                decision="blocked",
                release=release,
                provider_envelope=provider_envelope,
                transport_mode=safe_mode,
                timeout_ms=timeout_ms,
                retry_attempts=retry_attempts,
                idempotency_key=safe_idempotency_key,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        return _result(
            decision="planned",
            release=release,
            provider_envelope=provider_envelope,
            transport_mode=safe_mode,
            timeout_ms=timeout_ms,
            retry_attempts=retry_attempts,
            idempotency_key=safe_idempotency_key,
            adapter_plan_id=_adapter_plan_id(
                release=release,
                provider_envelope=provider_envelope,
                transport_mode=safe_mode,
                timeout_ms=timeout_ms,
                retry_attempts=retry_attempts,
                idempotency_key=safe_idempotency_key,
            ),
            adapter_plan_ready=True,
            release_bound=True,
            provider_envelope_bound=True,
        )


def _release_reasons(
    *,
    release: Optional[LiveExecutorReleaseResult],
    provider_envelope: LiveProviderRequestResult,
) -> tuple[str, ...]:
    if release is None:
        return ("executor_release_required",)
    reasons = []
    if release.decision != "release_ready" or not release.executor_release_granted:
        reasons.append("executor_release_not_ready")
    if release.executor_kind != "provider":
        reasons.append("executor_kind_not_provider")
    if release.envelope_id != provider_envelope.request_envelope_id:
        reasons.append("release_envelope_mismatch")
    if release.network_opened or release.handler_executed or release.live_transport_enabled:
        reasons.append("executor_release_side_effect_detected")
    if release.credential_material_accessed or release.raw_secret_returned:
        reasons.append("executor_release_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _provider_envelope_reasons(provider_envelope: LiveProviderRequestResult) -> tuple[str, ...]:
    reasons = []
    if provider_envelope.decision != "prepared" or not provider_envelope.request_prepared:
        reasons.append("provider_envelope_not_prepared")
    if not provider_envelope.secret_material_verified:
        reasons.append("provider_secret_material_not_verified")
    if provider_envelope.provider_invoked or provider_envelope.network_opened:
        reasons.append("provider_envelope_side_effect_detected")
    if provider_envelope.credential_material_accessed or provider_envelope.raw_secret_returned:
        reasons.append("provider_envelope_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _policy_reasons(
    transport_mode: str,
    timeout_ms: int,
    retry_attempts: int,
    idempotency_key: str,
) -> tuple[str, ...]:
    reasons = []
    if transport_mode not in _TRANSPORT_MODES:
        reasons.append("unsupported_transport_mode")
    if transport_mode == "live":
        reasons.append("provider_live_transport_not_implemented")
    if timeout_ms <= 0 or timeout_ms > _MAX_TIMEOUT_MS:
        reasons.append("timeout_out_of_bounds")
    if retry_attempts < 0 or retry_attempts > _MAX_RETRY_ATTEMPTS:
        reasons.append("retry_attempts_out_of_bounds")
    if idempotency_key == "":
        reasons.append("idempotency_key_required")
    return tuple(dict.fromkeys(reasons))


def _adapter_plan_id(
    *,
    release: Optional[LiveExecutorReleaseResult],
    provider_envelope: LiveProviderRequestResult,
    transport_mode: str,
    timeout_ms: int,
    retry_attempts: int,
    idempotency_key: str,
) -> str:
    payload = {
        "idempotency_key": idempotency_key,
        "release_id": None if release is None else release.release_id,
        "request_envelope_id": provider_envelope.request_envelope_id,
        "retry_attempts": retry_attempts,
        "timeout_ms": timeout_ms,
        "transport_mode": transport_mode,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-provider-adapter-plan-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveProviderAdapterDecision,
    release: Optional[LiveExecutorReleaseResult],
    provider_envelope: LiveProviderRequestResult,
    transport_mode: str,
    timeout_ms: int,
    retry_attempts: int,
    idempotency_key: str,
    adapter_plan_id: Optional[str] = None,
    blocked_reasons: tuple[str, ...] = (),
    adapter_plan_ready: bool = False,
    release_bound: bool = False,
    provider_envelope_bound: bool = False,
) -> LiveProviderAdapterResult:
    mode: Optional[ProviderTransportMode] = transport_mode if transport_mode in _TRANSPORT_MODES else None
    result = LiveProviderAdapterResult(
        decision=decision,
        adapter_plan_id=adapter_plan_id,
        release_id=None if release is None else release.release_id,
        request_envelope_id=provider_envelope.request_envelope_id,
        provider_kind=provider_envelope.provider_kind,
        model_id=provider_envelope.model_id,
        endpoint_host=provider_envelope.endpoint_host,
        transport_mode=mode,
        timeout_ms=timeout_ms,
        retry_attempts=retry_attempts,
        idempotency_key=idempotency_key,
        blocked_reasons=blocked_reasons,
        adapter_plan_ready=adapter_plan_ready,
        release_bound=release_bound,
        provider_envelope_bound=provider_envelope_bound,
        live_transport_requested=transport_mode == "live",
        execution_allowed=release is not None and release.execution_allowed and decision == "planned",
        authority_granted=False,
        live_transport_enabled=False,
        network_opened=False,
        handler_executed=False,
        external_delivery_opened=False,
        credential_material_accessed=False,
        raw_secret_returned=False,
        live_production_claimed=False,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _no_secret_echo(result: LiveProviderAdapterResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
