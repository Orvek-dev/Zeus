from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent import ZeusAgent
from zeus_agent.gateway_cockpit_runtime import GatewayCockpitRuntime


def test_gateway_cockpit_reports_adapter_breadth_without_delivery() -> None:
    # Given: the user asks for gateway cockpit overview.
    result = GatewayCockpitRuntime().build()

    # Then: Zeus exposes adapter breadth while keeping external delivery closed.
    assert result.decision == "report"
    assert result.adapter_count == 12
    assert result.fake_smoke_adapter_count == 3
    assert result.selected_adapter is None
    assert result.auth_required is True
    assert result.pairing_required is True
    assert result.delivery_target_allowlist_required is True
    assert "zeus gateway --adapter-id slack --json" in result.recommended_next_commands
    assert result.external_delivery_opened is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_gateway_cockpit_inspects_fake_smoke_adapter() -> None:
    # Given: the user inspects a known fake-smoke gateway adapter.
    result = GatewayCockpitRuntime().build(adapter_id="slack")

    # Then: Zeus returns the adapter contract without sending a message.
    assert result.decision == "report"
    assert result.selected_adapter is not None
    assert result.selected_adapter["adapter_id"] == "slack"
    assert result.selected_adapter["fake_smoke_enabled"] is True
    assert result.selected_adapter["auth_required"] is True
    assert result.selected_adapter["pairing_required"] is True
    assert result.external_delivery_opened is False
    assert result.network_opened is False


def test_gateway_cockpit_blocks_unknown_adapter() -> None:
    # Given: the user asks for an unknown gateway adapter.
    result = GatewayCockpitRuntime().build(adapter_id="unknown")

    # Then: the cockpit fails closed instead of fabricating adapter state.
    assert result.decision == "blocked"
    assert result.selected_adapter is None
    assert result.blocked_reasons == ("unknown_gateway_adapter",)
    assert result.live_production_claimed is False


def test_cli_exposes_gateway_cockpit() -> None:
    # Given: the user opens gateway cockpit inspection from CLI.
    completed = subprocess.run(
        [sys.executable, "-m", "zeus_agent", "gateway", "--adapter-id", "slack", "--json"],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    # Then: the CLI exposes adapter requirements without delivery side effects.
    assert payload["decision"] == "report"
    assert payload["selected_adapter"]["adapter_id"] == "slack"
    assert payload["selected_adapter"]["fake_smoke_enabled"] is True
    assert payload["external_delivery_opened"] is False


def test_python_library_exposes_gateway_cockpit() -> None:
    # Given: a Python user wants gateway status.
    payload = ZeusAgent().gateway_status(adapter_id="slack")

    # Then: the library returns the same JSON-compatible adapter inspection.
    assert payload["decision"] == "report"
    assert payload["selected_adapter"]["adapter_id"] == "slack"
    assert payload["live_production_claimed"] is False
