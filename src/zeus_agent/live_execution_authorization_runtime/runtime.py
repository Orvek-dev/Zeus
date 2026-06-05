from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_operator_proof_runtime import LiveOperatorProofResult
from zeus_agent.security.credentials import redact_secret_spans

LiveExecutionAuthorizationDecision = Literal["authorization_ready", "blocked"]
EnvelopeKind = Literal["provider", "gateway", "mcp"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_ENVELOPE_KINDS: Final = frozenset(("provider", "gateway", "mcp"))
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


class LiveExecutionAuthorizationResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveExecutionAuthorizationDecision
    authorization_id: Optional[str]
    envelope_kind: Optional[EnvelopeKind]
    envelope_id: Optional[str]
    operator_proof_id: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    authorization_envelope_ready: bool = False
    operator_proof_bound: bool = False
    required_risks_acknowledged: bool = False
    executor_release_granted: bool = False
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

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveExecutionAuthorizationRuntime:
    def authorize(
        self,
        *,
        envelope_kind: str,
        envelope: dict[str, JsonValue],
        operator_proof: Optional[LiveOperatorProofResult],
        required_risks: tuple[str, ...],
    ) -> LiveExecutionAuthorizationResult:
        safe_kind = envelope_kind.strip()
        safe_envelope = _safe_envelope(envelope)
        envelope_id = _envelope_id(kind=safe_kind, envelope=safe_envelope)
        reasons = []
        if safe_kind not in _ENVELOPE_KINDS:
            reasons.append("unsupported_authorization_envelope_kind")
        reasons.extend(_envelope_reasons(kind=safe_kind, envelope=safe_envelope))
        reasons.extend(_operator_proof_reasons(operator_proof, required_risks=required_risks))
        if reasons:
            return _result(
                decision="blocked",
                envelope_kind=safe_kind,
                envelope_id=envelope_id,
                operator_proof=operator_proof,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        return _result(
            decision="authorization_ready",
            envelope_kind=safe_kind,
            envelope_id=envelope_id,
            operator_proof=operator_proof,
            authorization_id=_authorization_id(
                envelope_kind=safe_kind,
                envelope_id=envelope_id,
                operator_proof=operator_proof,
                required_risks=required_risks,
            ),
            authorization_envelope_ready=True,
            operator_proof_bound=True,
            required_risks_acknowledged=True,
        )


def _safe_envelope(envelope: dict[str, JsonValue]) -> dict[str, JsonValue]:
    safe_payload: dict[str, JsonValue] = {}
    for key, value in envelope.items():
        safe_payload[redact_secret_spans(str(key))] = _safe_json_value(value)
    return safe_payload


def _safe_json_value(value: JsonValue) -> JsonValue:
    if isinstance(value, str):
        return redact_secret_spans(value)
    if isinstance(value, list):
        return [_safe_json_value(item) for item in value]
    if isinstance(value, dict):
        return {redact_secret_spans(str(key)): _safe_json_value(item) for key, item in value.items()}
    return value


def _envelope_id(*, kind: str, envelope: dict[str, JsonValue]) -> Optional[str]:
    key_by_kind = {
        "provider": "request_envelope_id",
        "gateway": "delivery_envelope_id",
        "mcp": "request_envelope_id",
    }
    key = key_by_kind.get(kind)
    if key is None:
        return None
    value = envelope.get(key)
    return value if isinstance(value, str) and value.strip() != "" else None


def _envelope_reasons(*, kind: str, envelope: dict[str, JsonValue]) -> tuple[str, ...]:
    if kind not in _ENVELOPE_KINDS:
        return ()
    reasons = []
    if envelope.get("decision") != "prepared":
        reasons.append("execution_envelope_not_prepared")
    prepared_key = {
        "provider": "request_prepared",
        "gateway": "delivery_prepared",
        "mcp": "request_prepared",
    }[kind]
    if not bool(envelope.get(prepared_key, False)):
        reasons.append("execution_envelope_not_prepared")
    for key in _side_effect_keys(kind):
        if bool(envelope.get(key, False)):
            reasons.append("execution_envelope_side_effect_detected")
    if _envelope_id(kind=kind, envelope=envelope) is None:
        reasons.append("execution_envelope_id_missing")
    return tuple(dict.fromkeys(reasons))


def _side_effect_keys(kind: str) -> tuple[str, ...]:
    common = (
        "credential_material_accessed",
        "raw_secret_returned",
        "network_opened",
        "handler_executed",
        "external_delivery_opened",
        "execution_allowed",
        "authority_granted",
        "live_transport_enabled",
        "live_production_claimed",
    )
    kind_specific = {
        "provider": ("provider_invoked",),
        "gateway": ("delivery_attempted",),
        "mcp": ("server_started", "resources_enabled", "prompts_enabled", "tool_invoked"),
    }.get(kind, ())
    return common + kind_specific


def _operator_proof_reasons(
    operator_proof: Optional[LiveOperatorProofResult],
    *,
    required_risks: tuple[str, ...],
) -> tuple[str, ...]:
    if operator_proof is None:
        return ("operator_proof_required",)
    reasons = []
    if operator_proof.decision != "recorded" or not operator_proof.operator_reviewed:
        reasons.append("operator_proof_not_recorded")
    acknowledged = set(operator_proof.reviewed_risks)
    if not set(required_risks).issubset(acknowledged):
        reasons.append("required_risk_not_acknowledged")
    if operator_proof.proof_material_accessed or operator_proof.credential_material_accessed:
        reasons.append("operator_proof_side_effect_detected")
    if operator_proof.network_opened or operator_proof.external_delivery_opened:
        reasons.append("operator_proof_side_effect_detected")
    if operator_proof.live_production_claimed:
        reasons.append("operator_proof_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def _authorization_id(
    *,
    envelope_kind: str,
    envelope_id: Optional[str],
    operator_proof: Optional[LiveOperatorProofResult],
    required_risks: tuple[str, ...],
) -> str:
    payload = {
        "envelope_id": envelope_id,
        "envelope_kind": envelope_kind,
        "operator_proof_hash": None if operator_proof is None else operator_proof.proof_hash,
        "required_risks": required_risks,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-execution-authorization-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveExecutionAuthorizationDecision,
    envelope_kind: str,
    envelope_id: Optional[str],
    operator_proof: Optional[LiveOperatorProofResult],
    authorization_id: Optional[str] = None,
    blocked_reasons: tuple[str, ...] = (),
    authorization_envelope_ready: bool = False,
    operator_proof_bound: bool = False,
    required_risks_acknowledged: bool = False,
) -> LiveExecutionAuthorizationResult:
    kind: Optional[EnvelopeKind] = envelope_kind if envelope_kind in _ENVELOPE_KINDS else None
    result = LiveExecutionAuthorizationResult(
        decision=decision,
        authorization_id=authorization_id,
        envelope_kind=kind,
        envelope_id=envelope_id,
        operator_proof_id=None if operator_proof is None else operator_proof.proof_id,
        blocked_reasons=blocked_reasons,
        authorization_envelope_ready=authorization_envelope_ready,
        operator_proof_bound=operator_proof_bound,
        required_risks_acknowledged=required_risks_acknowledged,
        executor_release_granted=False,
        provider_invoked=False,
        delivery_attempted=False,
        tool_invoked=False,
        server_started=False,
        resources_enabled=False,
        prompts_enabled=False,
        execution_allowed=False,
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


def _no_secret_echo(result: LiveExecutionAuthorizationResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
