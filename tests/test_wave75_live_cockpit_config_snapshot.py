from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime
from zeus_agent.setup_runtime import setup_apply


def test_live_cockpit_reports_local_configuration_snapshot(tmp_path: Path) -> None:
    _seed_setup(tmp_path)

    result = LiveCockpitRuntime(home=tmp_path).build()

    assert result.decision == "report"
    assert result.configuration_context["model_preference"]["provider_id"] == "openrouter"
    assert result.configuration_context["mcp_config"]["configured_server_count"] == 1
    assert result.configuration_context["gateway_config"]["configured_target_count"] == 1
    assert result.configuration_context["gateway_config"]["configured_targets"][0]["target"] == "slack://ops"
    assert result.configuration_context["network_opened"] is False
    assert result.configuration_context["external_delivery_opened"] is False
    assert result.configuration_context["credential_material_accessed"] is False
    assert result.live_production_claimed is False


def test_cli_live_reports_configuration_snapshot_with_home(tmp_path: Path) -> None:
    _seed_setup(tmp_path)
    runner = CliRunner()

    completed = runner.invoke(app, ["live", "--home", str(tmp_path), "--json"])

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["configuration_context"]["model_preference"]["provider_id"] == "openrouter"
    assert payload["configuration_context"]["mcp_config"]["configured_server_count"] == 1
    assert payload["configuration_context"]["gateway_config"]["configured_target_count"] == 1
    assert payload["network_opened"] is False
    assert payload["live_production_claimed"] is False


def test_python_library_live_status_reports_configuration_snapshot(tmp_path: Path) -> None:
    _seed_setup(tmp_path)

    payload = ZeusAgent(home=tmp_path).live_status()

    assert payload["configuration_context"]["model_preference"]["provider_id"] == "openrouter"
    assert payload["configuration_context"]["mcp_config"]["configured_server_count"] == 1
    assert payload["configuration_context"]["gateway_config"]["configured_target_count"] == 1
    assert payload["external_delivery_opened"] is False
    assert payload["live_production_claimed"] is False


def _seed_setup(home: Path) -> None:
    setup_apply(
        home=home,
        provider_id="openrouter/qwen",
        mcp=True,
        mcp_servers=("github",),
        gateway=True,
        gateway_adapter="slack",
        gateway_target="slack://ops",
    )
