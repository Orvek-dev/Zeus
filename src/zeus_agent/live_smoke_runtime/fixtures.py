from __future__ import annotations

from datetime import datetime, timezone
from typing import Final, Optional

from zeus_agent.live_beta_runtime import (
    LiveBetaActivationRequest,
    LiveBetaActivationResult,
    LiveBetaActivationRuntime,
)
from zeus_agent.mcp_runtime import McpDiscoverySnapshot, normalize_tools_list_result
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.security.credentials import redact_secret_spans

_NOW: Final = datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc)
_ISSUED_AT: Final = datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc)
_EXPIRES_AT: Final = datetime(2026, 6, 5, 0, 0, tzinfo=timezone.utc)
_EVIDENCE_TARGET: Final = "mneme.wave40.live_smoke"


def activate_fake_provider(
    provider_approval_receipt_id: Optional[str],
) -> LiveBetaActivationResult:
    request = LiveBetaActivationRequest(
        activation_id="wave40.provider.activation",
        surface_kind="provider",
        surface_id="provider.external.openai",
        capability_id="provider.external.generate",
        evidence_target=_EVIDENCE_TARGET,
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
        approval_receipt_id=provider_approval_receipt_id,
        probe_healthy=True,
        source_pinned=True,
    )
    return LiveBetaActivationRuntime().activate(request, lease=_provider_lease(), now=_NOW)


def activate_fake_gateway(
    *,
    approval_receipt_id: Optional[str],
    delivery_target: str,
    allowlisted_targets: tuple[str, ...],
) -> LiveBetaActivationResult:
    request = LiveBetaActivationRequest(
        activation_id="wave40.gateway.activation",
        surface_kind="gateway",
        surface_id="gateway.slack",
        capability_id="gateway.webhook.dispatch",
        evidence_target=_EVIDENCE_TARGET,
        credential_scope="external.gateway.readonly",
        network_host="gateway.local",
        approval_receipt_id=approval_receipt_id,
        probe_healthy=True,
        delivery_target=redact_secret_spans(delivery_target),
        allowlisted_delivery_targets=allowlisted_targets,
    )
    return LiveBetaActivationRuntime().activate(request, lease=_gateway_lease(), now=_NOW)


def build_fake_mcp_discovery() -> McpDiscoverySnapshot:
    return normalize_tools_list_result(
        {
            "tools": [
                {
                    "name": "repo_search",
                    "description": "Search repository issues.",
                    "inputSchema": {"type": "object"},
                    "annotations": {"destructiveHint": True},
                },
            ],
            "listChanged": True,
        },
        server_id="mcp.github",
        server_label="github",
        transport="stdio",
        trusted_server=False,
    )


def _provider_lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave40.lease.provider",
        objective_id="wave40.objective.provider",
        principal_id="wave40.principal.provider",
        run_id="wave40.run.provider",
        allowed_capabilities=("provider.external.generate",),
        credential_scopes=("external.openai.readonly",),
        network_hosts=("api.openai.local",),
        budget_limit=10,
        evidence_target=_EVIDENCE_TARGET,
        live_transport_allowed=True,
        issued_at=_ISSUED_AT,
        expires_at=_EXPIRES_AT,
    )


def _gateway_lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave40.lease.gateway",
        objective_id="wave40.objective.gateway",
        principal_id="wave40.principal.gateway",
        run_id="wave40.run.gateway",
        allowed_capabilities=("gateway.webhook.dispatch",),
        credential_scopes=("external.gateway.readonly",),
        network_hosts=("gateway.local",),
        budget_limit=10,
        evidence_target=_EVIDENCE_TARGET,
        live_transport_allowed=True,
        issued_at=_ISSUED_AT,
        expires_at=_EXPIRES_AT,
    )
