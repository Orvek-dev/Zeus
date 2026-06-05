from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_execution_authorization_runtime import LiveExecutionAuthorizationResult
from zeus_agent.security.credentials import redact_secret_spans

LiveExecutorReleaseDecision = Literal["release_ready", "blocked"]
ExecutorKind = Literal["provider", "gateway", "mcp"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_EXECUTOR_KINDS: Final = frozenset(("provider", "gateway", "mcp"))
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


class LiveExecutorReleaseResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveExecutorReleaseDecision
    release_id: Optional[str]
    authorization_id: Optional[str]
    envelope_id: Optional[str]
    executor_kind: Optional[ExecutorKind]
    release_ref: Optional[str]
    idempotency_key: str
    blocked_reasons: tuple[str, ...] = ()
    release_envelope_ready: bool = False
    executor_release_granted: bool = False
    execution_allowed: bool = False
    authority_granted: bool = False
    live_transport_enabled: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveExecutorReleaseRuntime:
    def release(
        self,
        *,
        authorization: Optional[LiveExecutionAuthorizationResult],
        executor_kind: str,
        release_ref: str,
        idempotency_key: str,
    ) -> LiveExecutorReleaseResult:
        safe_executor_kind = executor_kind.strip()
        safe_release_ref = _safe_optional(release_ref)
        safe_idempotency_key = redact_secret_spans(idempotency_key.strip())
        reasons = list(_authorization_reasons(authorization, executor_kind=safe_executor_kind))
        if safe_executor_kind not in _EXECUTOR_KINDS:
            reasons.append("unsupported_executor_kind")
        if safe_release_ref is None:
            reasons.append("release_ref_required")
        if safe_idempotency_key == "":
            reasons.append("idempotency_key_required")
        if reasons:
            return _result(
                decision="blocked",
                authorization=authorization,
                executor_kind=safe_executor_kind,
                release_ref=safe_release_ref,
                idempotency_key=safe_idempotency_key,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        return _result(
            decision="release_ready",
            authorization=authorization,
            executor_kind=safe_executor_kind,
            release_ref=safe_release_ref,
            idempotency_key=safe_idempotency_key,
            release_id=_release_id(
                authorization=authorization,
                executor_kind=safe_executor_kind,
                release_ref=safe_release_ref,
                idempotency_key=safe_idempotency_key,
            ),
            release_envelope_ready=True,
            executor_release_granted=True,
            execution_allowed=True,
        )


def _authorization_reasons(
    authorization: Optional[LiveExecutionAuthorizationResult],
    *,
    executor_kind: str,
) -> tuple[str, ...]:
    if authorization is None:
        return ("execution_authorization_required",)
    reasons = []
    if authorization.decision != "authorization_ready" or not authorization.authorization_envelope_ready:
        reasons.append("execution_authorization_not_ready")
    if authorization.envelope_kind != executor_kind:
        reasons.append("executor_kind_mismatch")
    if not authorization.operator_proof_bound or not authorization.required_risks_acknowledged:
        reasons.append("execution_authorization_incomplete")
    if authorization.executor_release_granted or authorization.execution_allowed:
        reasons.append("execution_authorization_already_released")
    if _authorization_side_effect_seen(authorization):
        reasons.append("execution_authorization_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def _authorization_side_effect_seen(authorization: LiveExecutionAuthorizationResult) -> bool:
    return bool(
        authorization.network_opened
        or authorization.handler_executed
        or authorization.external_delivery_opened
        or authorization.credential_material_accessed
        or authorization.raw_secret_returned
        or authorization.live_transport_enabled
        or authorization.live_production_claimed
    )


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    if redacted == "":
        return None
    return redacted


def _release_id(
    *,
    authorization: Optional[LiveExecutionAuthorizationResult],
    executor_kind: str,
    release_ref: Optional[str],
    idempotency_key: str,
) -> str:
    payload = {
        "authorization_id": None if authorization is None else authorization.authorization_id,
        "executor_kind": executor_kind,
        "idempotency_key": idempotency_key,
        "release_ref": release_ref,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-executor-release-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveExecutorReleaseDecision,
    authorization: Optional[LiveExecutionAuthorizationResult],
    executor_kind: str,
    release_ref: Optional[str],
    idempotency_key: str,
    release_id: Optional[str] = None,
    blocked_reasons: tuple[str, ...] = (),
    release_envelope_ready: bool = False,
    executor_release_granted: bool = False,
    execution_allowed: bool = False,
) -> LiveExecutorReleaseResult:
    kind: Optional[ExecutorKind] = executor_kind if executor_kind in _EXECUTOR_KINDS else None
    result = LiveExecutorReleaseResult(
        decision=decision,
        release_id=release_id,
        authorization_id=None if authorization is None else authorization.authorization_id,
        envelope_id=None if authorization is None else authorization.envelope_id,
        executor_kind=kind,
        release_ref=release_ref,
        idempotency_key=idempotency_key,
        blocked_reasons=blocked_reasons,
        release_envelope_ready=release_envelope_ready,
        executor_release_granted=executor_release_granted,
        execution_allowed=execution_allowed,
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


def _no_secret_echo(result: LiveExecutorReleaseResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
