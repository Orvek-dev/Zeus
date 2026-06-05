from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_gateway_adapter_runtime import LiveGatewayAdapterResult
from zeus_agent.live_mcp_adapter_runtime import LiveMcpAdapterResult
from zeus_agent.live_provider_adapter_runtime import LiveProviderAdapterResult
from zeus_agent.live_transport_opt_in_runtime import LiveTransportOptInResult
from zeus_agent.security.credentials import redact_secret_spans

LiveTransportActivationDecision = Literal["activation_ready", "blocked"]
LiveTransportAdapterKind = Literal["provider", "gateway", "mcp"]
LiveAdapterPlan = Union[LiveProviderAdapterResult, LiveGatewayAdapterResult, LiveMcpAdapterResult]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_ADAPTER_KINDS: Final = frozenset(("provider", "gateway", "mcp"))
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


class LiveTransportActivationResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveTransportActivationDecision
    activation_id: Optional[str]
    opt_in_id: Optional[str]
    adapter_kind: Optional[LiveTransportAdapterKind]
    adapter_plan_id: Optional[str]
    activation_ref: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    opt_in_bound: bool = False
    adapter_plan_bound: bool = False
    transport_activation_ready: bool = False
    live_transport_requested: bool = False
    live_transport_opted_in: bool = False
    live_transport_authorized: bool = False
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


class LiveTransportActivationRuntime:
    def plan(
        self,
        *,
        opt_in: Optional[LiveTransportOptInResult],
        adapter_kind: str,
        adapter_plan: LiveAdapterPlan,
        activation_ref: str,
    ) -> LiveTransportActivationResult:
        safe_kind = adapter_kind.strip()
        safe_ref = _safe_optional(activation_ref)
        adapter_plan_id, plan_reasons = _adapter_plan_id_and_reasons(
            adapter_kind=safe_kind,
            adapter_plan=adapter_plan,
        )
        reasons = list(_opt_in_reasons(opt_in=opt_in, adapter_kind=safe_kind, adapter_plan_id=adapter_plan_id))
        reasons.extend(plan_reasons)
        if safe_kind not in _ADAPTER_KINDS:
            reasons.append("unsupported_adapter_kind")
        if safe_ref is None:
            reasons.append("activation_ref_required")
        if reasons:
            return _result(
                decision="blocked",
                opt_in=opt_in,
                adapter_kind=safe_kind,
                adapter_plan_id=adapter_plan_id,
                activation_ref=safe_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        return _result(
            decision="activation_ready",
            opt_in=opt_in,
            adapter_kind=safe_kind,
            adapter_plan_id=adapter_plan_id,
            activation_ref=safe_ref,
            activation_id=_activation_id(
                opt_in=opt_in,
                adapter_kind=safe_kind,
                adapter_plan_id=adapter_plan_id,
                activation_ref=safe_ref,
            ),
            opt_in_bound=True,
            adapter_plan_bound=True,
            transport_activation_ready=True,
            live_transport_requested=True,
            live_transport_opted_in=True,
            live_transport_authorized=True,
        )


def _opt_in_reasons(
    *,
    opt_in: Optional[LiveTransportOptInResult],
    adapter_kind: str,
    adapter_plan_id: Optional[str],
) -> tuple[str, ...]:
    if opt_in is None:
        return ("live_transport_opt_in_required",)
    reasons = []
    if opt_in.decision != "opt_in_ready" or not opt_in.live_transport_opted_in:
        reasons.append("live_transport_opt_in_not_ready")
    if opt_in.adapter_kind != adapter_kind:
        reasons.append("opt_in_adapter_kind_mismatch")
    if opt_in.adapter_plan_id != adapter_plan_id:
        reasons.append("opt_in_adapter_plan_mismatch")
    if _opt_in_side_effect_seen(opt_in):
        reasons.append("live_transport_opt_in_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def _opt_in_side_effect_seen(opt_in: LiveTransportOptInResult) -> bool:
    return bool(
        opt_in.live_transport_enabled
        or opt_in.network_opened
        or opt_in.handler_executed
        or opt_in.external_delivery_opened
        or opt_in.credential_material_accessed
        or opt_in.raw_secret_returned
        or opt_in.live_production_claimed
    )


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


def _generic_adapter_plan_id(adapter_plan: LiveAdapterPlan) -> Optional[str]:
    return getattr(adapter_plan, "adapter_plan_id", None)


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _activation_id(
    *,
    opt_in: Optional[LiveTransportOptInResult],
    adapter_kind: str,
    adapter_plan_id: Optional[str],
    activation_ref: Optional[str],
) -> str:
    payload = {
        "activation_ref": activation_ref,
        "adapter_kind": adapter_kind,
        "adapter_plan_id": adapter_plan_id,
        "opt_in_id": None if opt_in is None else opt_in.opt_in_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-transport-activation-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveTransportActivationDecision,
    opt_in: Optional[LiveTransportOptInResult],
    adapter_kind: str,
    adapter_plan_id: Optional[str],
    activation_ref: Optional[str],
    activation_id: Optional[str] = None,
    blocked_reasons: tuple[str, ...] = (),
    opt_in_bound: bool = False,
    adapter_plan_bound: bool = False,
    transport_activation_ready: bool = False,
    live_transport_requested: bool = False,
    live_transport_opted_in: bool = False,
    live_transport_authorized: bool = False,
) -> LiveTransportActivationResult:
    kind: Optional[LiveTransportAdapterKind] = adapter_kind if adapter_kind in _ADAPTER_KINDS else None
    result = LiveTransportActivationResult(
        decision=decision,
        activation_id=activation_id,
        opt_in_id=None if opt_in is None else opt_in.opt_in_id,
        adapter_kind=kind,
        adapter_plan_id=adapter_plan_id,
        activation_ref=activation_ref,
        blocked_reasons=blocked_reasons,
        opt_in_bound=opt_in_bound,
        adapter_plan_bound=adapter_plan_bound,
        transport_activation_ready=transport_activation_ready,
        live_transport_requested=live_transport_requested,
        live_transport_opted_in=live_transport_opted_in,
        live_transport_authorized=live_transport_authorized,
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


def _no_secret_echo(result: LiveTransportActivationResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
