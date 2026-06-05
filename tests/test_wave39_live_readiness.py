from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from zeus_agent import ZeusAgent
from zeus_agent.live_beta_runtime import LiveBetaActivationRequest, LiveBetaActivationRuntime
from zeus_agent.live_readiness_runtime import LiveReadinessRuntime
from zeus_agent.mcp_runtime import normalize_tools_list_result
from zeus_agent.runtime_lease import RuntimeLease


def test_live_readiness_report_summarizes_default_surfaces_without_live_claim() -> None:
    # Given: Zeus has no explicit live beta activation yet.
    report = LiveReadinessRuntime().build_report()

    # Then: readiness is inspectable without opening live surfaces.
    assert report.surface_count >= 8
    assert report.live_beta_count == 0
    assert report.blocked_count >= 1
    assert report.live_production_claimed is False
    assert report.network_opened is False
    assert report.handler_executed is False
    assert report.external_delivery_opened is False
    assert report.user_approval_required is True
    assert "approval_required" in report.recommended_next_actions


def test_live_readiness_report_absorbs_beta_activation_and_mcp_discovery_metadata() -> None:
    # Given: one provider beta activation and one MCP discovery snapshot are available.
    activation = LiveBetaActivationRuntime().activate(
        _provider_request(),
        lease=_lease(live_transport_allowed=True),
        now=_now(),
    )
    discovery = normalize_tools_list_result(
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

    # When: readiness is built from current local evidence.
    report = LiveReadinessRuntime().build_report(
        beta_activations=(activation,),
        mcp_discoveries=(discovery,),
    )
    provider = report.surface_by_id("provider.external.openai")
    mcp = report.surface_by_id("mcp.github")

    # Then: beta and discovery state are visible but production remains unclaimed.
    assert provider.state == "live_beta"
    assert provider.production_ready is False
    assert mcp.state == "dry_run"
    assert mcp.metadata["tool_count"] == 1
    assert mcp.metadata["trusted_annotations_applied"] is False
    assert report.live_beta_count == 1
    assert report.live_production_claimed is False


def test_live_readiness_report_redacts_secret_like_surface_metadata() -> None:
    # Given: a readiness note accidentally contains secret-like text.
    raw_secret = "sk-wave39-secret"
    report = LiveReadinessRuntime().build_report(
        extra_notes=("operator pasted {0}".format(raw_secret),),
    )
    serialized = report.model_dump_json()

    # Then: the report preserves no raw secret echo.
    assert report.no_secret_echo is True
    assert raw_secret not in serialized
    assert "sk-...redacted" in serialized


def test_cli_and_library_expose_live_readiness_report() -> None:
    # Given: a user asks for live readiness from CLI and Python.
    completed = subprocess.run(
        [sys.executable, "-m", "zeus_agent", "live-readiness", "--json"],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    cli_payload = json.loads(completed.stdout)
    library_payload = ZeusAgent().live_readiness()

    # Then: both surfaces expose the same no-production readiness contract.
    assert cli_payload["surface_count"] >= 8
    assert library_payload["surface_count"] >= 8
    assert cli_payload["live_production_claimed"] is False
    assert library_payload["live_production_claimed"] is False
    assert cli_payload["network_opened"] is False
    assert library_payload["handler_executed"] is False


def _provider_request() -> LiveBetaActivationRequest:
    return LiveBetaActivationRequest(
        activation_id="wave39.provider.activation",
        surface_kind="provider",
        surface_id="provider.external.openai",
        capability_id="provider.external.generate",
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
        evidence_target="mneme.wave39.live_readiness",
        approval_receipt_id="approval.wave39.provider",
        probe_healthy=True,
        source_pinned=True,
    )


def _lease(*, live_transport_allowed: bool) -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave39.lease.live_readiness",
        objective_id="wave39.objective.live_readiness",
        principal_id="wave39.principal.operator",
        run_id="wave39.run.live_readiness",
        allowed_capabilities=("provider.external.generate",),
        credential_scopes=("external.openai.readonly",),
        network_hosts=("api.openai.local",),
        budget_limit=100,
        evidence_target="mneme.wave39.live_readiness",
        live_transport_allowed=live_transport_allowed,
        issued_at=datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 5, 0, 0, tzinfo=timezone.utc),
    )


def _now() -> datetime:
    return datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc)
