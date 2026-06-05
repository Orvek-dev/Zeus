from __future__ import annotations

import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.gateway_runtime import plan_gateway_adapter_delivery
from zeus_agent.live_beta_runtime import LiveBetaActivationResult
from zeus_agent.live_readiness_runtime import LiveReadinessReport, LiveReadinessRuntime
from zeus_agent.mcp_runtime import McpDiscoverySnapshot

from .fixtures import activate_fake_gateway, activate_fake_provider, build_fake_mcp_discovery

LiveOptInSmokeScenario = Literal["happy", "blocked"]
GatewayDeliveryDecision = Literal["planned", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
_GATEWAY_ADAPTER_ID: Final = "slack"
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


class LiveOptInSmokeResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: Literal["passed", "blocked"]
    provider: LiveBetaActivationResult
    gateway: LiveBetaActivationResult
    mcp_discovery: McpDiscoverySnapshot
    readiness: LiveReadinessReport
    gateway_delivery_decision: GatewayDeliveryDecision
    gateway_delivery_reasons: tuple[str, ...] = ()
    blocked_reasons: tuple[str, ...] = ()
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveOptInSmokeRuntime:
    def run(
        self,
        *,
        provider_approval_receipt_id: Optional[str] = "approval.wave40.provider",
        gateway_approval_receipt_id: Optional[str] = "approval.wave40.gateway",
        gateway_delivery_target: str = "slack://engineering",
        allowlisted_gateway_targets: tuple[str, ...] = ("slack://engineering",),
    ) -> LiveOptInSmokeResult:
        provider = activate_fake_provider(provider_approval_receipt_id)
        gateway = activate_fake_gateway(
            approval_receipt_id=gateway_approval_receipt_id,
            delivery_target=gateway_delivery_target,
            allowlisted_targets=allowlisted_gateway_targets,
        )
        gateway_plan = plan_gateway_adapter_delivery(
            adapter_id=_GATEWAY_ADAPTER_ID,
            target=gateway_delivery_target,
            allowlisted_targets=allowlisted_gateway_targets,
            auth_receipt_id="gateway.auth.wave40",
            pairing_receipt_id="gateway.pair.wave40",
        )
        mcp_discovery = build_fake_mcp_discovery()
        readiness = LiveReadinessRuntime().build_report(
            beta_activations=(provider, gateway),
            mcp_discoveries=(mcp_discovery,),
        )
        result = _compose_result(
            provider=provider,
            gateway=gateway,
            mcp_discovery=mcp_discovery,
            readiness=readiness,
            gateway_plan=gateway_plan,
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def run_live_optin_smoke(
    *,
    scenario: LiveOptInSmokeScenario = "happy",
) -> LiveOptInSmokeResult:
    if scenario == "happy":
        return LiveOptInSmokeRuntime().run()
    return LiveOptInSmokeRuntime().run(
        provider_approval_receipt_id=None,
        gateway_delivery_target="slack://ops",
        allowlisted_gateway_targets=("slack://engineering",),
    )


def _compose_result(
    *,
    provider: LiveBetaActivationResult,
    gateway: LiveBetaActivationResult,
    mcp_discovery: McpDiscoverySnapshot,
    readiness: LiveReadinessReport,
    gateway_plan: dict[str, JsonValue],
) -> LiveOptInSmokeResult:
    gateway_delivery_reasons = tuple(
        str(reason) for reason in gateway_plan.get("blocked_reasons", ())
    )
    blocked_reasons = _blocked_reasons(
        provider=provider,
        gateway=gateway,
        gateway_delivery_reasons=gateway_delivery_reasons,
        mcp_discovery=mcp_discovery,
    )
    gateway_decision = _gateway_delivery_decision(gateway_plan)
    if gateway_decision != "planned":
        blocked_reasons = tuple(
            dict.fromkeys((*blocked_reasons, *("gateway:{0}".format(reason) for reason in gateway_delivery_reasons)))
        )
    decision: Literal["passed", "blocked"] = "blocked" if blocked_reasons else "passed"
    return LiveOptInSmokeResult(
        decision=decision,
        provider=provider,
        gateway=gateway,
        mcp_discovery=mcp_discovery,
        readiness=readiness,
        gateway_delivery_decision=gateway_decision,
        gateway_delivery_reasons=gateway_delivery_reasons,
        blocked_reasons=blocked_reasons,
        network_opened=provider.network_opened or gateway.network_opened or readiness.network_opened,
        handler_executed=provider.handler_executed or gateway.handler_executed or readiness.handler_executed,
        external_delivery_opened=(
            provider.external_delivery_opened
            or gateway.external_delivery_opened
            or readiness.external_delivery_opened
        ),
        credential_material_accessed=(
            provider.credential_material_accessed
            or gateway.credential_material_accessed
            or readiness.credential_material_accessed
        ),
        live_production_claimed=(
            provider.live_production_claimed
            or gateway.live_production_claimed
            or mcp_discovery.live_production_claimed
            or readiness.live_production_claimed
        ),
    )


def _blocked_reasons(
    *,
    provider: LiveBetaActivationResult,
    gateway: LiveBetaActivationResult,
    gateway_delivery_reasons: tuple[str, ...],
    mcp_discovery: McpDiscoverySnapshot,
) -> tuple[str, ...]:
    reasons = [
        *("provider:{0}".format(reason) for reason in provider.reasons),
        *("gateway:{0}".format(reason) for reason in gateway.reasons),
        *("gateway:{0}".format(reason) for reason in gateway_delivery_reasons),
    ]
    if mcp_discovery.decision != "allowed":
        reasons.append("mcp:{0}".format(mcp_discovery.reason))
    return tuple(dict.fromkeys(reasons))


def _gateway_delivery_decision(gateway_plan: dict[str, JsonValue]) -> GatewayDeliveryDecision:
    decision = gateway_plan.get("decision")
    if decision == "planned":
        return "planned"
    return "blocked"


def _no_secret_echo(result: LiveOptInSmokeResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
