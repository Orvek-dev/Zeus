from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_executor_release_runtime import LiveExecutorReleaseResult
from zeus_agent.live_loopback_executor_runtime.envelopes import envelope_id_and_reasons
from zeus_agent.security.credentials import redact_secret_spans

LiveLoopbackExecutorDecision = Literal["executed", "blocked"]
ExecutorKind = Literal["provider", "gateway", "mcp"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_EXECUTOR_KINDS: Final = frozenset(("provider", "gateway", "mcp"))
_CLEANUP_RECEIPT: Final = "loopback-no-runtime-resources"
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


class LiveLoopbackExecutorResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveLoopbackExecutorDecision
    execution_id: Optional[str]
    release_id: Optional[str]
    envelope_id: Optional[str]
    executor_kind: Optional[ExecutorKind]
    execution_ref: Optional[str]
    cleanup_receipt: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    executor_release_bound: bool = False
    envelope_bound: bool = False
    loopback_only: bool = True
    loopback_executed: bool = False
    provider_invoked: bool = False
    delivery_attempted: bool = False
    tool_invoked: bool = False
    server_started: bool = False
    resources_enabled: bool = False
    prompts_enabled: bool = False
    execution_allowed: bool = False
    authority_granted: bool = False
    live_transport_enabled: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    output: Optional[dict[str, JsonValue]] = None

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveLoopbackExecutorRuntime:
    def execute(
        self,
        *,
        release: Optional[LiveExecutorReleaseResult],
        envelope_kind: str,
        envelope: dict[str, JsonValue],
        execution_ref: str,
    ) -> LiveLoopbackExecutorResult:
        safe_kind = envelope_kind.strip()
        safe_execution_ref = _safe_optional(execution_ref)
        envelope_id, envelope_reasons = envelope_id_and_reasons(
            envelope_kind=safe_kind,
            envelope=envelope,
        )
        reasons = list(_release_reasons(release=release, envelope_kind=safe_kind))
        reasons.extend(envelope_reasons)
        if safe_kind not in _EXECUTOR_KINDS:
            reasons.append("unsupported_executor_kind")
        if safe_execution_ref is None:
            reasons.append("execution_ref_required")
        if release is not None and envelope_id is not None and release.envelope_id != envelope_id:
            reasons.append("release_envelope_mismatch")
        if reasons:
            return _result(
                decision="blocked",
                release=release,
                executor_kind=safe_kind,
                envelope_id=envelope_id,
                execution_ref=safe_execution_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        return _result(
            decision="executed",
            release=release,
            executor_kind=safe_kind,
            envelope_id=envelope_id,
            execution_ref=safe_execution_ref,
            execution_id=_execution_id(
                release=release,
                envelope_id=envelope_id,
                executor_kind=safe_kind,
                execution_ref=safe_execution_ref,
            ),
            executor_release_bound=True,
            envelope_bound=True,
            loopback_executed=True,
            handler_executed=True,
            execution_allowed=True,
            output={
                "mode": "loopback",
                "envelope_digest": _digest(envelope),
                "cleanup": _CLEANUP_RECEIPT,
            },
        )


def _release_reasons(
    *,
    release: Optional[LiveExecutorReleaseResult],
    envelope_kind: str,
) -> tuple[str, ...]:
    if release is None:
        return ("executor_release_required",)
    reasons = []
    if (
        release.decision != "release_ready"
        or not release.release_envelope_ready
        or not release.executor_release_granted
        or not release.execution_allowed
    ):
        reasons.append("executor_release_not_ready")
    if release.executor_kind != envelope_kind:
        reasons.append("executor_kind_mismatch")
    if _release_side_effect_seen(release):
        reasons.append("executor_release_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def _release_side_effect_seen(release: LiveExecutorReleaseResult) -> bool:
    return bool(
        release.live_transport_enabled
        or release.network_opened
        or release.handler_executed
        or release.external_delivery_opened
        or release.credential_material_accessed
        or release.raw_secret_returned
        or release.live_production_claimed
    )


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _digest(value: dict[str, JsonValue]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _execution_id(
    *,
    release: Optional[LiveExecutorReleaseResult],
    envelope_id: Optional[str],
    executor_kind: str,
    execution_ref: Optional[str],
) -> str:
    payload = {
        "envelope_id": envelope_id,
        "executor_kind": executor_kind,
        "execution_ref": execution_ref,
        "release_id": None if release is None else release.release_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-loopback-execution-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveLoopbackExecutorDecision,
    release: Optional[LiveExecutorReleaseResult],
    executor_kind: str,
    envelope_id: Optional[str],
    execution_ref: Optional[str],
    execution_id: Optional[str] = None,
    blocked_reasons: tuple[str, ...] = (),
    executor_release_bound: bool = False,
    envelope_bound: bool = False,
    loopback_executed: bool = False,
    handler_executed: bool = False,
    execution_allowed: bool = False,
    output: Optional[dict[str, JsonValue]] = None,
) -> LiveLoopbackExecutorResult:
    kind: Optional[ExecutorKind] = executor_kind if executor_kind in _EXECUTOR_KINDS else None
    result = LiveLoopbackExecutorResult(
        decision=decision,
        execution_id=execution_id,
        release_id=None if release is None else release.release_id,
        envelope_id=envelope_id,
        executor_kind=kind,
        execution_ref=execution_ref,
        cleanup_receipt=_CLEANUP_RECEIPT if decision == "executed" else None,
        blocked_reasons=blocked_reasons,
        executor_release_bound=executor_release_bound,
        envelope_bound=envelope_bound,
        loopback_executed=loopback_executed,
        handler_executed=handler_executed,
        execution_allowed=execution_allowed,
        authority_granted=False,
        live_transport_enabled=False,
        network_opened=False,
        external_delivery_opened=False,
        credential_material_accessed=False,
        raw_secret_returned=False,
        live_production_claimed=False,
        output=output,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _no_secret_echo(result: LiveLoopbackExecutorResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
