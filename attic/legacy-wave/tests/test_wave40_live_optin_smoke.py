from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent import ZeusAgent
from zeus_agent.live_smoke_runtime import LiveOptInSmokeRuntime, run_live_optin_smoke


def test_live_optin_smoke_passes_fake_provider_mcp_and_gateway_bundle() -> None:
    # Given: local fake live opt-in smoke is requested with all required receipts.
    result = run_live_optin_smoke(scenario="happy")

    # Then: Zeus proves the beta flow without opening production side effects.
    assert result.decision == "passed"
    assert result.provider.decision == "live_beta"
    assert result.gateway.decision == "live_beta"
    assert result.mcp_discovery.decision == "allowed"
    assert result.gateway_delivery_decision == "planned"
    assert result.readiness.live_beta_count == 2
    assert result.network_opened is False
    assert result.handler_executed is False
    assert result.external_delivery_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False
    assert result.no_secret_echo is True


def test_live_optin_smoke_blocks_missing_approval_and_gateway_allowlist_mismatch() -> None:
    # Given: adversarial opt-in smoke inputs include missing approval and unsafe target.
    raw_secret = "sk-" + "wave40-secret"
    result = LiveOptInSmokeRuntime().run(
        provider_approval_receipt_id=None,
        gateway_delivery_target="slack://ops?token={0}".format(raw_secret),
        allowlisted_gateway_targets=("slack://engineering",),
    )
    serialized = result.model_dump_json()

    # Then: the bundle fails closed and does not echo raw secret material.
    assert result.decision == "blocked"
    assert "provider:missing_approval" in result.blocked_reasons
    assert "gateway:delivery_target_not_allowlisted" in result.blocked_reasons
    assert result.provider.live_beta_claimed is False
    assert result.gateway_delivery_decision == "blocked"
    assert result.network_opened is False
    assert result.handler_executed is False
    assert result.external_delivery_opened is False
    assert result.no_secret_echo is True
    assert raw_secret not in serialized
    assert "[redacted-secret]" in serialized


def test_cli_exposes_live_optin_smoke_bundle() -> None:
    # Given: the operator asks for the local fake opt-in smoke through CLI.
    completed = subprocess.run(
        [sys.executable, "-m", "zeus_agent", "live-optin-smoke", "--scenario", "happy", "--json"],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    # Then: the CLI proves beta smoke while preserving production boundaries.
    assert payload["decision"] == "passed"
    assert payload["provider"]["decision"] == "live_beta"
    assert payload["gateway"]["decision"] == "live_beta"
    assert payload["mcp_discovery"]["decision"] == "allowed"
    assert payload["live_production_claimed"] is False
    assert payload["network_opened"] is False


def test_python_library_exposes_live_optin_smoke_bundle() -> None:
    # Given: a Python user wants the same opt-in smoke evidence.
    payload = ZeusAgent().live_optin_smoke()

    # Then: the library returns a JSON-compatible no-production smoke report.
    assert payload["decision"] == "passed"
    assert payload["readiness"]["live_beta_count"] == 2
    assert payload["live_production_claimed"] is False
