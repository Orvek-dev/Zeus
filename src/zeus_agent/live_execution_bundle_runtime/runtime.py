from __future__ import annotations

import hashlib
import json
from typing import Optional

from zeus_agent.live_execution_bundle_runtime.models import (
    LiveExecutionBundleDecision,
    LiveExecutionBundleResult,
    LiveExecutionSurfaceSummary,
)
from zeus_agent.live_execution_bundle_runtime.surfaces import (
    source_secret_reasons,
    surface_reasons,
    surface_summaries,
)
from zeus_agent.live_gateway_credentialed_http_runtime import LiveGatewayCredentialedHttpResult
from zeus_agent.live_mcp_credentialed_http_runtime import LiveMcpCredentialedHttpResult
from zeus_agent.live_provider_credentialed_http_runtime import LiveProviderCredentialedHttpResult


class LiveExecutionBundleRuntime:
    def summarize(
        self,
        *,
        provider_result: Optional[LiveProviderCredentialedHttpResult],
        gateway_result: Optional[LiveGatewayCredentialedHttpResult],
        mcp_result: Optional[LiveMcpCredentialedHttpResult],
        bundle_ref: str,
    ) -> LiveExecutionBundleResult:
        safe_ref = bundle_ref.strip()
        surfaces = surface_summaries(provider_result, gateway_result, mcp_result)
        reasons = list(_bundle_reasons(surfaces, safe_ref))
        reasons.extend(source_secret_reasons(provider_result, gateway_result, mcp_result))
        blocked_reasons = tuple(dict.fromkeys(reasons))
        decision: LiveExecutionBundleDecision = "blocked" if blocked_reasons else "summarized"
        return LiveExecutionBundleResult(
            decision=decision,
            bundle_id=_bundle_id(safe_ref, surfaces) if decision == "summarized" else None,
            bundle_ref=safe_ref,
            surfaces=surfaces,
            surface_count=len(surfaces),
            executed_count=sum(1 for surface in surfaces if surface.decision == "executed"),
            blocked_count=sum(1 for surface in surfaces if surface.decision == "blocked"),
            local_loopback_count=sum(1 for surface in surfaces if surface.local_http_loopback),
            credentialed_surface_count=sum(1 for surface in surfaces if surface.credentialed_http),
            blocked_reasons=blocked_reasons,
            recommended_next_commands=_recommended_next_commands(decision),
            network_opened=any(surface.network_opened for surface in surfaces),
            non_loopback_network_opened=any(surface.non_loopback_network_opened for surface in surfaces),
            handler_executed=any(surface.handler_executed for surface in surfaces),
            external_delivery_opened=any(surface.external_delivery_opened for surface in surfaces),
            credential_material_accessed=any(surface.credential_material_accessed for surface in surfaces),
            raw_secret_returned=any(surface.raw_secret_returned for surface in surfaces),
            no_secret_echo=not any("secret_echo_detected" in reason for reason in blocked_reasons),
            live_production_claimed=any(surface.live_production_claimed for surface in surfaces),
            safety_notes=_safety_notes(),
        )


def _bundle_reasons(surfaces: tuple[LiveExecutionSurfaceSummary, ...], bundle_ref: str) -> tuple[str, ...]:
    reasons: list[str] = []
    if bundle_ref == "":
        reasons.append("bundle_ref_required")
    if not surfaces:
        reasons.append("execution_result_required")
    for surface in surfaces:
        reasons.extend(surface_reasons(surface))
    return tuple(reasons)


def _bundle_id(bundle_ref: str, surfaces: tuple[LiveExecutionSurfaceSummary, ...]) -> str:
    payload = {
        "bundle_ref": bundle_ref,
        "surfaces": [surface.model_dump(mode="json") for surface in surfaces],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-execution-bundle-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _recommended_next_commands(decision: LiveExecutionBundleDecision) -> tuple[str, ...]:
    if decision == "blocked":
        return ("zeus live-readiness --json", "zeus live --include-smoke --scenario blocked --json")
    return (
        "zeus live-readiness --json",
        "zeus live --include-smoke --scenario happy --json",
        "zeus live-transport-teardown-record --json",
    )


def _safety_notes() -> tuple[str, ...]:
    return (
        "bundle summarizes prior local loopback execution evidence only",
        "bundle does not open transport, release credentials, start MCP servers, or claim production readiness",
    )
