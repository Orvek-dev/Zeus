from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_gateway_adapter_runtime import LiveGatewayAdapterResult
from zeus_agent.live_mcp_adapter_runtime import LiveMcpAdapterResult
from zeus_agent.live_operator_proof_runtime import LiveOperatorProofResult
from zeus_agent.live_provider_adapter_runtime import LiveProviderAdapterResult
from zeus_agent.security.credentials import redact_secret_spans

LiveTransportOptInDecision = Literal["opt_in_ready", "blocked"]
LiveTransportAdapterKind = Literal["provider", "gateway", "mcp"]
LiveTransportMode = Literal["live"]
LiveAdapterPlan = Union[LiveProviderAdapterResult, LiveGatewayAdapterResult, LiveMcpAdapterResult]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_ADAPTER_KINDS: Final = frozenset(("provider", "gateway", "mcp"))
_REQUIRED_RISKS: Final = {
    "provider": ("network", "credential_material_access", "external_provider_inference", "live_transport"),
    "gateway": ("network", "credential_material_access", "external_delivery", "live_transport"),
    "mcp": ("network", "credential_material_access", "mcp_remote_tool", "live_transport"),
}
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


class LiveTransportOptInResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveTransportOptInDecision
    opt_in_id: Optional[str]
    adapter_kind: Optional[LiveTransportAdapterKind]
    adapter_plan_id: Optional[str]
    operator_proof_id: Optional[str]
    opt_in_ref: Optional[str]
    requested_transport_mode: Optional[LiveTransportMode]
    required_risks: tuple[str, ...] = ()
    blocked_reasons: tuple[str, ...] = ()
    adapter_plan_bound: bool = False
    operator_proof_bound: bool = False
    required_risks_acknowledged: bool = False
    live_transport_requested: bool = False
    live_transport_opted_in: bool = False
    live_transport_enabled: bool = False
    execution_allowed: bool = False
    authority_granted: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveTransportOptInRuntime:
    def record(
        self,
        *,
        adapter_kind: str,
        adapter_plan: LiveAdapterPlan,
        operator_proof: Optional[LiveOperatorProofResult],
        opt_in_ref: str,
        requested_transport_mode: str,
    ) -> LiveTransportOptInResult:
        safe_kind = adapter_kind.strip()
        safe_ref = _safe_optional(opt_in_ref)
        safe_mode = requested_transport_mode.strip()
        required_risks = _required_risks(safe_kind)
        adapter_plan_id, plan_reasons = _adapter_plan_id_and_reasons(
            adapter_kind=safe_kind,
            adapter_plan=adapter_plan,
        )
        reasons = list(plan_reasons)
        reasons.extend(_proof_reasons(operator_proof=operator_proof, required_risks=required_risks))
        if safe_kind not in _ADAPTER_KINDS:
            reasons.append("unsupported_adapter_kind")
        if safe_ref is None:
            reasons.append("opt_in_ref_required")
        if safe_mode != "live":
            reasons.append("live_transport_request_required")
        if reasons:
            return _result(
                decision="blocked",
                adapter_kind=safe_kind,
                adapter_plan_id=adapter_plan_id,
                operator_proof=operator_proof,
                opt_in_ref=safe_ref,
                requested_transport_mode=safe_mode,
                required_risks=required_risks,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        return _result(
            decision="opt_in_ready",
            adapter_kind=safe_kind,
            adapter_plan_id=adapter_plan_id,
            operator_proof=operator_proof,
            opt_in_ref=safe_ref,
            requested_transport_mode=safe_mode,
            required_risks=required_risks,
            opt_in_id=_opt_in_id(
                adapter_kind=safe_kind,
                adapter_plan_id=adapter_plan_id,
                operator_proof=operator_proof,
                opt_in_ref=safe_ref,
            ),
            adapter_plan_bound=True,
            operator_proof_bound=True,
            required_risks_acknowledged=True,
            live_transport_requested=True,
            live_transport_opted_in=True,
        )


def _required_risks(adapter_kind: str) -> tuple[str, ...]:
    return _REQUIRED_RISKS.get(adapter_kind, ())


def _adapter_plan_id_and_reasons(
    *,
    adapter_kind: str,
    adapter_plan: LiveAdapterPlan,
) -> tuple[Optional[str], tuple[str, ...]]:
    if adapter_kind == "provider" and isinstance(adapter_plan, LiveProviderAdapterResult):
        return adapter_plan.adapter_plan_id, _provider_plan_reasons(adapter_plan)
    if adapter_kind == "gateway" and isinstance(adapter_plan, LiveGatewayAdapterResult):
        return adapter_plan.adapter_plan_id, _gateway_plan_reasons(adapter_plan)
    if adapter_kind == "mcp" and isinstance(adapter_plan, LiveMcpAdapterResult):
        return adapter_plan.adapter_plan_id, _mcp_plan_reasons(adapter_plan)
    return _generic_adapter_plan_id(adapter_plan), ("adapter_plan_kind_mismatch",)


def _provider_plan_reasons(adapter_plan: LiveProviderAdapterResult) -> tuple[str, ...]:
    reasons = []
    if adapter_plan.decision != "planned" or not adapter_plan.adapter_plan_ready:
        reasons.append("adapter_plan_not_ready")
    if adapter_plan.provider_invoked or adapter_plan.network_opened or adapter_plan.live_transport_enabled:
        reasons.append("adapter_plan_side_effect_detected")
    if adapter_plan.credential_material_accessed or adapter_plan.raw_secret_returned:
        reasons.append("adapter_plan_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _gateway_plan_reasons(adapter_plan: LiveGatewayAdapterResult) -> tuple[str, ...]:
    reasons = []
    if adapter_plan.decision != "planned" or not adapter_plan.adapter_plan_ready:
        reasons.append("adapter_plan_not_ready")
    if adapter_plan.delivery_attempted or adapter_plan.external_delivery_opened:
        reasons.append("adapter_plan_side_effect_detected")
    if adapter_plan.network_opened or adapter_plan.live_transport_enabled:
        reasons.append("adapter_plan_side_effect_detected")
    if adapter_plan.credential_material_accessed or adapter_plan.raw_secret_returned:
        reasons.append("adapter_plan_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _mcp_plan_reasons(adapter_plan: LiveMcpAdapterResult) -> tuple[str, ...]:
    reasons = []
    if adapter_plan.decision != "planned" or not adapter_plan.adapter_plan_ready:
        reasons.append("adapter_plan_not_ready")
    if adapter_plan.server_started or adapter_plan.tool_invoked or adapter_plan.network_opened:
        reasons.append("adapter_plan_side_effect_detected")
    if adapter_plan.resources_enabled or adapter_plan.prompts_enabled:
        reasons.append("adapter_plan_side_effect_detected")
    if adapter_plan.credential_material_accessed or adapter_plan.raw_secret_returned:
        reasons.append("adapter_plan_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _proof_reasons(
    *,
    operator_proof: Optional[LiveOperatorProofResult],
    required_risks: tuple[str, ...],
) -> tuple[str, ...]:
    if operator_proof is None:
        return ("operator_proof_required",)
    reasons = []
    if operator_proof.decision != "recorded" or not operator_proof.operator_reviewed:
        reasons.append("operator_proof_not_recorded")
    if not set(required_risks).issubset(set(operator_proof.reviewed_risks)):
        reasons.append("required_risk_not_acknowledged")
    if operator_proof.execution_authorized:
        reasons.append("operator_proof_must_not_authorize_execution")
    return tuple(dict.fromkeys(reasons))


def _generic_adapter_plan_id(adapter_plan: LiveAdapterPlan) -> Optional[str]:
    return getattr(adapter_plan, "adapter_plan_id", None)


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _opt_in_id(
    *,
    adapter_kind: str,
    adapter_plan_id: Optional[str],
    operator_proof: Optional[LiveOperatorProofResult],
    opt_in_ref: Optional[str],
) -> str:
    payload = {
        "adapter_kind": adapter_kind,
        "adapter_plan_id": adapter_plan_id,
        "operator_proof_id": None if operator_proof is None else operator_proof.proof_id,
        "opt_in_ref": opt_in_ref,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-transport-opt-in-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveTransportOptInDecision,
    adapter_kind: str,
    adapter_plan_id: Optional[str],
    operator_proof: Optional[LiveOperatorProofResult],
    opt_in_ref: Optional[str],
    requested_transport_mode: str,
    required_risks: tuple[str, ...],
    opt_in_id: Optional[str] = None,
    blocked_reasons: tuple[str, ...] = (),
    adapter_plan_bound: bool = False,
    operator_proof_bound: bool = False,
    required_risks_acknowledged: bool = False,
    live_transport_requested: bool = False,
    live_transport_opted_in: bool = False,
) -> LiveTransportOptInResult:
    kind: Optional[LiveTransportAdapterKind] = adapter_kind if adapter_kind in _ADAPTER_KINDS else None
    mode: Optional[LiveTransportMode] = requested_transport_mode if requested_transport_mode == "live" else None
    result = LiveTransportOptInResult(
        decision=decision,
        opt_in_id=opt_in_id,
        adapter_kind=kind,
        adapter_plan_id=adapter_plan_id,
        operator_proof_id=None if operator_proof is None else operator_proof.proof_id,
        opt_in_ref=opt_in_ref,
        requested_transport_mode=mode,
        required_risks=required_risks,
        blocked_reasons=blocked_reasons,
        adapter_plan_bound=adapter_plan_bound,
        operator_proof_bound=operator_proof_bound,
        required_risks_acknowledged=required_risks_acknowledged,
        live_transport_requested=live_transport_requested,
        live_transport_opted_in=live_transport_opted_in,
        live_transport_enabled=False,
        execution_allowed=False,
        authority_granted=False,
        network_opened=False,
        handler_executed=False,
        external_delivery_opened=False,
        credential_material_accessed=False,
        raw_secret_returned=False,
        live_production_claimed=False,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _no_secret_echo(result: LiveTransportOptInResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
