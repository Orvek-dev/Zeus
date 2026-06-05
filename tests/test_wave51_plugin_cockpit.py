from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent import ZeusAgent
from zeus_agent.plugin_cockpit_runtime import PluginCockpitRuntime


def test_plugin_cockpit_reports_supply_chain_controls_without_loading_plugins() -> None:
    result = PluginCockpitRuntime().build()

    assert result.decision == "report"
    assert result.plugin_count == 2
    assert result.quarantined_plugin_count == 1
    assert result.blocked_plugin_count == 1
    assert result.selected_plugin is None
    assert "zeus plugins --plugin-id safe-local --json" in result.recommended_next_commands
    assert result.tool_registration_allowed is False
    assert result.dependency_installed is False
    assert result.handler_executed is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_plugin_cockpit_inspects_quarantined_plugin_candidate() -> None:
    result = PluginCockpitRuntime().build(plugin_id="safe-local")

    assert result.decision == "report"
    assert result.selected_plugin is not None
    assert result.selected_plugin["plugin_id"] == "safe-local"
    assert result.selected_plugin["validation_decision"] == "quarantined"
    assert result.selected_plugin["tool_registration_allowed"] is False
    assert result.selected_plugin["quarantine_required"] is True
    assert result.selected_plugin["handler_executed"] is False


def test_plugin_cockpit_inspects_blocked_untrusted_plugin_without_secret_echo() -> None:
    raw_secret = "sk-" + "wave51-secret"
    result = PluginCockpitRuntime().build(plugin_id="untrusted-network")
    serialized = json.dumps(result.to_payload(), sort_keys=True)

    assert result.decision == "report"
    assert result.selected_plugin is not None
    assert result.selected_plugin["validation_decision"] == "blocked"
    assert "unsafe_permission" in result.selected_plugin["blocked_reasons"]
    assert "untrusted_dependency" in result.selected_plugin["blocked_reasons"]
    assert raw_secret not in serialized
    assert result.no_secret_echo is True
    assert result.network_opened is False


def test_plugin_cockpit_blocks_unknown_plugin_inspection() -> None:
    result = PluginCockpitRuntime().build(plugin_id="unknown")

    assert result.decision == "blocked"
    assert result.selected_plugin is None
    assert result.blocked_reasons == ("unknown_plugin",)
    assert result.tool_registration_allowed is False
    assert result.live_production_claimed is False


def test_cli_exposes_plugin_cockpit_inspection() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "zeus_agent", "plugins", "--plugin-id", "safe-local", "--json"],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["decision"] == "report"
    assert payload["selected_plugin"]["plugin_id"] == "safe-local"
    assert payload["selected_plugin"]["validation_decision"] == "quarantined"
    assert payload["tool_registration_allowed"] is False
    assert payload["handler_executed"] is False


def test_python_library_exposes_plugin_cockpit() -> None:
    payload = ZeusAgent().plugin_status(plugin_id="untrusted-network")

    assert payload["decision"] == "report"
    assert payload["selected_plugin"]["plugin_id"] == "untrusted-network"
    assert payload["selected_plugin"]["validation_decision"] == "blocked"
    assert payload["live_production_claimed"] is False
