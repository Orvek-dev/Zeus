from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.governed_live_connector_platform_runtime import build_governed_live_connector_platform
from zeus_agent.governed_live_slice_runtime import build_governed_live_slice
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v580_release_gate_reports_governed_live_connector_checkpoint() -> None:
    payload = build_release_gated_ulw_status(target_version="v5.8.0").to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v5.8.0"
    assert payload["release_stage"] == "governed_live_connector_platform"
    assert payload["governed_live_connector_platform_available"] is True
    assert payload["provider_connector_activation_available"] is True
    assert payload["mcp_connector_activation_available"] is True
    assert payload["gateway_loopback_connector_available"] is True
    assert payload["local_sandbox_connector_available"] is True
    assert payload["connector_broker_evidence_required"] is True
    assert payload["governed_live_connector_platform_ready"] is True
    assert payload["production_ready"] is False
    assert payload["next_version"] == "v6.0.0"


def test_connector_platform_reports_missing_governance_for_all_surfaces(tmp_path: Path) -> None:
    payload = build_governed_live_connector_platform(home=tmp_path, scenario="status").to_payload()

    assert payload["decision"] == "blocked"
    assert payload["target_version"] == "v5.8.0"
    assert payload["surfaces"] == ["provider", "mcp", "gateway", "local_sandbox"]
    assert payload["connectors_ready"] is False
    assert payload["missing_requirement_count"] >= 4
    assert "provider" in payload["blocked_surfaces"]
    assert "mcp" in payload["blocked_surfaces"]
    assert "gateway" in payload["blocked_surfaces"]
    assert "local_sandbox" in payload["blocked_surfaces"]
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False


def test_connector_platform_allows_trusted_local_smokes_through_broker_evidence(tmp_path: Path) -> None:
    payload = build_governed_live_connector_platform(home=tmp_path, scenario="trusted-local-smoke").to_payload()

    assert payload["decision"] == "ready"
    assert payload["connectors_ready"] is True
    assert payload["allowed_surfaces"] == ["provider", "mcp", "gateway", "local_sandbox"]
    assert payload["broker_evidence_bound_count"] == 4
    assert payload["handler_executed_count"] == 4
    assert payload["network_opened"] is False
    assert payload["external_delivery_opened"] is False
    assert payload["live_production_claimed"] is False


def test_governed_live_slice_supports_mcp_gateway_and_local_sandbox_smokes() -> None:
    for surface, capability_id in (
        ("mcp", "mcp.local-smoke"),
        ("gateway", "gateway.loopback-smoke"),
        ("local_sandbox", "local-sandbox.local-smoke"),
    ):
        payload = build_governed_live_slice(
            surface=surface,
            capability_id=capability_id,
            scenario="local-smoke",
            objective_run_id="run-v580",
            lease_ref="lease://v580/{0}".format(capability_id),
            approval_ref="approval://v580/{0}".format(capability_id),
            promotion_guard_ref="promotion-guard://v580/{0}".format(capability_id),
            broker_evidence_ref="broker-evidence://v580/{0}".format(capability_id),
            credential_scope="credential.{0}".format(capability_id),
            sandbox_policy_ref="sandbox://local/default-deny-egress",
            audit_receipt_ref="audit://v580/{0}".format(capability_id),
        ).to_payload()

        assert payload["decision"] == "allowed"
        assert payload["broker_evidence_bound"] is True
        assert payload["handler_executed"] is True
        assert payload["network_opened"] is False
        assert payload["live_production_claimed"] is False


def test_cli_and_library_expose_governed_live_connector_platform(tmp_path: Path) -> None:
    runner = CliRunner()
    completed = runner.invoke(
        app,
        [
            "governed-live-connectors",
            "--scenario",
            "trusted-local-smoke",
            "--home",
            str(tmp_path),
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).governed_live_connectors(
        scenario="trusted-local-smoke"
    )

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["target_version"] == "v5.8.0"
    assert library_payload["target_version"] == "v5.8.0"
    assert cli_payload["connectors_ready"] is True
    assert library_payload["connectors_ready"] is True
