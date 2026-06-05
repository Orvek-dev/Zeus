from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.gateway_settings_runtime import GatewaySettingsRuntime
from zeus_agent.live_dry_run_runtime import LiveDryRunRuntime
from zeus_agent.live_profile_runtime import LiveProfileRuntime
from zeus_agent.mcp_settings_runtime import McpSettingsRuntime
from zeus_agent.model_settings_runtime import ModelSettingsRuntime


def test_live_profile_absorbs_local_model_mcp_and_gateway_config(tmp_path: Path) -> None:
    _seed_local_config(tmp_path)

    result = LiveProfileRuntime(home=tmp_path).build(
        surface_id="gateway.slack",
        principal_id="wave73.principal.operator",
        objective_id="wave73.objective.live",
    )

    assert result.decision == "profile"
    assert result.preflight_request_template["delivery_target"] == "slack://ops"
    assert result.preflight_request_template["allowlisted_delivery_targets"] == ["slack://ops"]
    assert result.configuration_context["model_preference"]["provider_id"] == "openrouter"
    assert result.configuration_context["model_preference"]["model_id"] == "openrouter/qwen"
    assert result.configuration_context["mcp_config"]["configured_server_count"] == 1
    assert result.configuration_context["mcp_config"]["configured_server_ids"] == ["mcp.github"]
    assert result.configuration_context["gateway_config"]["configured_target_count"] == 1
    assert result.configuration_context["gateway_config"]["configured_targets"][0]["adapter_id"] == "slack"
    assert result.configuration_context["external_delivery_opened"] is False
    assert result.configuration_context["network_opened"] is False
    assert result.configuration_context["credential_material_accessed"] is False
    assert result.live_production_claimed is False


def test_live_profile_explicit_gateway_target_overrides_configured_default(tmp_path: Path) -> None:
    _seed_local_config(tmp_path)

    result = LiveProfileRuntime(home=tmp_path).build(
        surface_id="gateway.slack",
        principal_id="wave73.principal.operator",
        objective_id="wave73.objective.live",
        delivery_target="slack://engineering",
        allowlisted_delivery_targets=("slack://engineering",),
    )

    assert result.decision == "profile"
    assert result.preflight_request_template["delivery_target"] == "slack://engineering"
    assert result.preflight_request_template["allowlisted_delivery_targets"] == ["slack://engineering"]
    assert result.configuration_context["gateway_config"]["configured_targets"][0]["target"] == "slack://ops"


def test_live_dry_run_uses_absorbed_gateway_config_without_explicit_target(tmp_path: Path) -> None:
    _seed_local_config(tmp_path)

    result = LiveDryRunRuntime(home=tmp_path).run(
        surface_id="gateway.slack",
        principal_id="wave73.principal.operator",
        objective_id="wave73.objective.live",
        now=_now(),
    )

    assert result.decision == "planned"
    assert result.profile.preflight_request_template["delivery_target"] == "slack://ops"
    assert result.profile.configuration_context["gateway_config"]["configured_target_count"] == 1
    assert result.preflight.decision == "preflight_ready"
    assert result.execute_plan.decision == "planned"
    assert result.external_delivery_opened is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_cli_live_dry_run_absorbs_local_config(tmp_path: Path) -> None:
    _seed_local_config(tmp_path)
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-dry-run",
            "--surface-id",
            "gateway.slack",
            "--principal-id",
            "wave73.principal.operator",
            "--objective-id",
            "wave73.objective.live",
            "--home",
            str(tmp_path),
            "--now",
            "2026-06-04T12:00:00+00:00",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "planned"
    assert payload["profile"]["preflight_request_template"]["delivery_target"] == "slack://ops"
    assert payload["profile"]["configuration_context"]["gateway_config"]["configured_target_count"] == 1
    assert payload["network_opened"] is False
    assert payload["live_production_claimed"] is False


def test_python_library_live_dry_run_absorbs_local_config(tmp_path: Path) -> None:
    _seed_local_config(tmp_path)

    payload = ZeusAgent(home=tmp_path).live_dry_run(
        surface_id="gateway.slack",
        principal_id="wave73.principal.operator",
        objective_id="wave73.objective.live",
        now=_now(),
    )

    assert payload["decision"] == "planned"
    assert payload["profile"]["preflight_request_template"]["delivery_target"] == "slack://ops"
    assert payload["profile"]["configuration_context"]["model_preference"]["provider_id"] == "openrouter"
    assert payload["profile"]["configuration_context"]["mcp_config"]["configured_server_count"] == 1
    assert payload["live_production_claimed"] is False


def _seed_local_config(home: Path) -> None:
    ModelSettingsRuntime(home).set(provider_ref="openrouter/qwen")
    McpSettingsRuntime(home).add(server_ref="github")
    GatewaySettingsRuntime(home).add(adapter_ref="slack", target="slack://ops")


def _now() -> datetime:
    return datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
