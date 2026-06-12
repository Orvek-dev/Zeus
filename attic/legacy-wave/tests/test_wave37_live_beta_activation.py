from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from zeus_agent import ZeusAgent
from zeus_agent.live_beta_runtime import (
    LiveBetaActivationRequest,
    LiveBetaActivationRuntime,
)
from zeus_agent.runtime_lease import RuntimeLease


def test_provider_live_beta_requires_lease_approval_probe_and_source_pin() -> None:
    # Given: a provider live-beta request with explicit authority and approval.
    lease = _lease(
        capability_id="provider.external.generate",
        credential_scopes=("external.openai.readonly",),
        network_hosts=("api.openai.local",),
        live_transport_allowed=True,
    )
    request = LiveBetaActivationRequest(
        activation_id="wave37.provider.activation",
        surface_kind="provider",
        surface_id="provider.external.openai",
        capability_id="provider.external.generate",
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
        evidence_target="mneme.wave37.live_beta",
        approval_receipt_id="approval.wave37.provider",
        probe_healthy=True,
        source_pinned=True,
    )

    # When: Zeus evaluates beta activation.
    result = LiveBetaActivationRuntime().activate(
        request,
        lease=lease,
        now=_now(),
    )

    # Then: the activation is beta-only and never opens production side effects.
    assert result.decision == "live_beta"
    assert result.reasons == ()
    assert result.live_beta_claimed is True
    assert result.live_production_claimed is False
    assert result.lease_authorized is True
    assert result.approval_receipt_bound is True
    assert result.network_opened is False
    assert result.handler_executed is False
    assert result.external_delivery_opened is False
    assert result.credential_material_accessed is False
    assert result.no_secret_echo is True


def test_live_beta_blocks_missing_approval_and_non_live_lease() -> None:
    # Given: requests that omit approval or live transport lease authority.
    approved_request = _provider_request(approval_receipt_id="approval.wave37.provider")
    missing_approval = _provider_request(approval_receipt_id=None)
    live_lease = _lease(
        capability_id="provider.external.generate",
        credential_scopes=("external.openai.readonly",),
        network_hosts=("api.openai.local",),
        live_transport_allowed=True,
    )
    dry_lease = _lease(
        capability_id="provider.external.generate",
        credential_scopes=("external.openai.readonly",),
        network_hosts=("api.openai.local",),
        live_transport_allowed=False,
    )

    # When: both requests are evaluated.
    missing_approval_result = LiveBetaActivationRuntime().activate(
        missing_approval,
        lease=live_lease,
        now=_now(),
    )
    non_live_lease_result = LiveBetaActivationRuntime().activate(
        approved_request,
        lease=dry_lease,
        now=_now(),
    )

    # Then: both fail closed before beta or network activation.
    assert missing_approval_result.decision == "blocked"
    assert "missing_approval" in missing_approval_result.reasons
    assert missing_approval_result.live_beta_claimed is False
    assert non_live_lease_result.decision == "blocked"
    assert "live_network_without_scope" in non_live_lease_result.reasons
    assert non_live_lease_result.network_opened is False
    assert non_live_lease_result.handler_executed is False


def test_gateway_live_beta_requires_allowlisted_delivery_target() -> None:
    # Given: a gateway request with lease authority but a non-allowlisted target.
    lease = _lease(
        capability_id="gateway.webhook.dispatch",
        credential_scopes=("external.gateway.readonly",),
        network_hosts=("gateway.local",),
        live_transport_allowed=True,
    )
    request = LiveBetaActivationRequest(
        activation_id="wave37.gateway.activation",
        surface_kind="gateway",
        surface_id="gateway.slack",
        capability_id="gateway.webhook.dispatch",
        credential_scope="external.gateway.readonly",
        network_host="gateway.local",
        evidence_target="mneme.wave37.live_beta",
        approval_receipt_id="approval.wave37.gateway",
        probe_healthy=True,
        delivery_target="slack://ops",
        allowlisted_delivery_targets=("slack://engineering",),
    )

    # When: Zeus evaluates beta activation.
    result = LiveBetaActivationRuntime().activate(
        request,
        lease=lease,
        now=_now(),
    )

    # Then: external delivery remains closed.
    assert result.decision == "blocked"
    assert "delivery_target_not_allowlisted" in result.reasons
    assert result.external_delivery_opened is False
    assert result.network_opened is False
    assert result.live_beta_claimed is False


def test_live_beta_result_redacts_secret_like_inputs() -> None:
    # Given: secret-like material is accidentally placed in beta activation fields.
    raw_secret = "sk-wave37-secret"
    lease = _lease(
        capability_id="provider.external.generate",
        credential_scopes=("external.openai.readonly",),
        network_hosts=("api.openai.local",),
        live_transport_allowed=True,
    )
    request = LiveBetaActivationRequest(
        activation_id="wave37.secret.activation",
        surface_kind="provider",
        surface_id="provider.external.openai",
        capability_id="provider.external.generate",
        credential_scope=raw_secret,
        network_host="api.openai.local",
        evidence_target="mneme.wave37.live_beta",
        approval_receipt_id=raw_secret,
        probe_healthy=True,
        source_pinned=True,
    )

    # When: Zeus evaluates the request.
    result = LiveBetaActivationRuntime().activate(
        request,
        lease=lease,
        now=_now(),
    )
    serialized = json.dumps(result.to_payload(), sort_keys=True)

    # Then: unsafe credentials block and raw secret material is not echoed.
    assert result.decision == "blocked"
    assert "unsafe_credential" in result.reasons
    assert result.no_secret_echo is True
    assert raw_secret not in serialized
    assert "sk-...redacted" in serialized


def test_python_library_exposes_live_beta_activation_surface() -> None:
    # Given: a Python user wants to evaluate live beta readiness from ZeusAgent.
    agent = ZeusAgent()
    request = _provider_request(approval_receipt_id="approval.wave37.provider")

    # When: the library facade evaluates the request.
    payload = agent.live_beta_activate(
        request,
        lease=_lease(
            capability_id="provider.external.generate",
            credential_scopes=("external.openai.readonly",),
            network_hosts=("api.openai.local",),
            live_transport_allowed=True,
        ),
        now=_now(),
    )

    # Then: the facade reports beta readiness without claiming production.
    assert payload["decision"] == "live_beta"
    assert payload["live_beta_claimed"] is True
    assert payload["live_production_claimed"] is False
    assert agent.live_production_claimed is False


def test_cli_exposes_live_beta_activation_json_surface() -> None:
    # Given: a CLI caller supplies request and lease JSON for a beta activation check.
    request = _provider_request(approval_receipt_id="approval.wave37.provider")
    lease = _lease(
        capability_id="provider.external.generate",
        credential_scopes=("external.openai.readonly",),
        network_hosts=("api.openai.local",),
        live_transport_allowed=True,
    )

    # When: the Zeus CLI command is executed.
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live-beta-activate",
            "--request-json",
            request.model_dump_json(),
            "--lease-json",
            lease.model_dump_json(),
            "--now",
            _now().isoformat(),
            "--json",
        ],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    # Then: the CLI exposes the same beta-only decision and no-side-effect flags.
    assert payload["decision"] == "live_beta"
    assert payload["live_beta_claimed"] is True
    assert payload["live_production_claimed"] is False
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False


def _provider_request(approval_receipt_id: str | None) -> LiveBetaActivationRequest:
    return LiveBetaActivationRequest(
        activation_id="wave37.provider.activation",
        surface_kind="provider",
        surface_id="provider.external.openai",
        capability_id="provider.external.generate",
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
        evidence_target="mneme.wave37.live_beta",
        approval_receipt_id=approval_receipt_id,
        probe_healthy=True,
        source_pinned=True,
    )


def _lease(
    *,
    capability_id: str,
    credential_scopes: tuple[str, ...],
    network_hosts: tuple[str, ...],
    live_transport_allowed: bool,
) -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave37.lease.live_beta",
        objective_id="wave37.objective.live_beta",
        principal_id="wave37.principal.operator",
        run_id="wave37.run.live_beta",
        allowed_capabilities=(capability_id,),
        credential_scopes=credential_scopes,
        network_hosts=network_hosts,
        budget_limit=100,
        evidence_target="mneme.wave37.live_beta",
        live_transport_allowed=live_transport_allowed,
        issued_at=datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 5, 0, 0, tzinfo=timezone.utc),
    )


def _now() -> datetime:
    return datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc)
