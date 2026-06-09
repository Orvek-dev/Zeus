from __future__ import annotations

from pathlib import Path

from zeus_agent.governed_live_connector_platform_runtime.models import (
    ConnectorPlatformScenario,
    GovernedLiveConnectorPlatformResult,
)
from zeus_agent.governed_live_slice_runtime import build_governed_live_slice
from zeus_agent.governed_live_slice_runtime.models import GovernedLiveSliceResult

_CONNECTORS: tuple[tuple[str, str], ...] = (
    ("provider", "provider.local-smoke"),
    ("mcp", "mcp.local-smoke"),
    ("gateway", "gateway.loopback-smoke"),
    ("local_sandbox", "local-sandbox.local-smoke"),
)


def build_governed_live_connector_platform(
    *,
    home: Path,
    scenario: ConnectorPlatformScenario = "status",
) -> GovernedLiveConnectorPlatformResult:
    del home
    results = tuple(_slice(surface, capability_id, scenario) for surface, capability_id in _CONNECTORS)
    allowed = tuple(result.surface for result in results if result.decision == "allowed")
    blocked = tuple(result.surface for result in results if result.decision != "allowed")
    ready = not blocked and scenario != "public-boundary"
    return GovernedLiveConnectorPlatformResult(
        decision="ready" if ready else "blocked",
        scenario=scenario,
        surfaces=tuple(surface for surface, _capability_id in _CONNECTORS),
        allowed_surfaces=allowed,
        blocked_surfaces=blocked,
        connector_results=results,
        connectors_ready=ready,
        provider_connector_ready="provider" in allowed,
        mcp_connector_ready="mcp" in allowed,
        gateway_connector_ready="gateway" in allowed,
        local_sandbox_connector_ready="local_sandbox" in allowed,
        broker_evidence_bound_count=sum(1 for result in results if result.broker_evidence_bound),
        missing_requirement_count=sum(len(result.missing_requirements) for result in results),
        handler_executed_count=sum(1 for result in results if result.handler_executed),
        network_opened=any(result.network_opened for result in results),
        credential_material_accessed=any(result.credential_material_accessed for result in results),
        external_delivery_opened=any(result.external_delivery_opened for result in results),
        handler_executed=any(result.handler_executed for result in results),
        live_production_claimed=any(result.live_production_claimed for result in results),
        no_secret_echo=all(result.no_secret_echo for result in results),
    )


def _slice(
    surface: str,
    capability_id: str,
    scenario: ConnectorPlatformScenario,
) -> GovernedLiveSliceResult:
    if scenario != "trusted-local-smoke":
        return build_governed_live_slice(
            surface=surface,
            capability_id=capability_id,
            scenario="local-smoke",
        )
    return build_governed_live_slice(
        surface=surface,
        capability_id=capability_id,
        scenario="local-smoke",
        objective_run_id="run-v580",
        lease_ref=_ref("lease", capability_id),
        approval_ref=_ref("approval", capability_id),
        promotion_guard_ref=_ref("promotion-guard", capability_id),
        broker_evidence_ref=_ref("broker-evidence", capability_id),
        credential_scope=_credential_scope(capability_id),
        sandbox_policy_ref="sandbox://local/default-deny-egress",
        audit_receipt_ref=_ref("audit", capability_id),
    )


def _ref(kind: str, capability_id: str) -> str:
    if capability_id == "provider.local-smoke":
        mapping = {
            "lease": "lease://v210/provider-local-smoke",
            "approval": "approval://v210/provider-local-smoke",
            "promotion-guard": "promotion-guard://v210/provider-local-smoke",
            "broker-evidence": "broker-evidence://v210/provider-local-smoke",
            "audit": "audit://v580/provider.local-smoke",
        }
        return mapping[kind]
    return "{0}://v580/{1}".format(kind, capability_id)


def _credential_scope(capability_id: str) -> str:
    if capability_id == "provider.local-smoke":
        return "credential.local-smoke"
    return "credential.{0}".format(capability_id)
