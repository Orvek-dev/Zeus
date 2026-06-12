from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.gateway_settings_runtime import GatewaySettingsRuntime
from zeus_agent.live_dry_run_runtime import LiveDryRunRuntime
from zeus_agent.setup_runtime import setup_apply


def test_setup_apply_writes_model_mcp_and_gateway_local_config(tmp_path: Path) -> None:
    result = setup_apply(
        home=tmp_path,
        provider_id="openrouter/qwen",
        mcp=True,
        mcp_servers=("github",),
        gateway=True,
        gateway_adapter="slack",
        gateway_target="slack://ops",
    )

    assert result["decision"] == "configured"
    assert result["settings_written"] is True
    assert result["model_settings"]["provider_id"] == "openrouter"
    assert result["mcp_settings"]["configured_server_count"] == 1
    assert result["gateway_settings"]["configured_target_count"] == 1
    assert result["gateway_settings"]["configured_targets"][0]["adapter_id"] == "slack"
    assert result["gateway_settings"]["external_delivery_opened"] is False
    assert result["network_opened"] is False
    assert result["credential_material_accessed"] is False
    assert result["live_production_claimed"] is False

    dry_run = LiveDryRunRuntime(home=tmp_path).run(
        surface_id="gateway.slack",
        principal_id="wave74.principal.operator",
        objective_id="wave74.objective.live",
        now=_now(),
    )
    assert dry_run.decision == "planned"
    assert dry_run.profile.preflight_request_template["delivery_target"] == "slack://ops"


def test_setup_apply_blocks_unknown_gateway_adapter_without_gateway_write(tmp_path: Path) -> None:
    result = setup_apply(
        home=tmp_path,
        provider_id="openrouter/qwen",
        mcp=True,
        mcp_servers=("github",),
        gateway=True,
        gateway_adapter="unknown-gateway",
        gateway_target="slack://ops",
    )

    assert result["decision"] == "blocked"
    assert "gateway:unknown_gateway_adapter" in result["blocked_reasons"]
    assert result["settings_written"] is False
    assert result["gateway_settings"]["configured_target_count"] == 0
    assert GatewaySettingsRuntime(tmp_path).list().configured_target_count == 0
    assert result["live_production_claimed"] is False


def test_cli_setup_write_applies_gateway_config_for_live_dry_run(tmp_path: Path) -> None:
    runner = CliRunner()

    configured = runner.invoke(
        app,
        [
            "setup",
            "--write",
            "--provider-id",
            "openrouter/qwen",
            "--mcp",
            "--mcp-server",
            "github",
            "--gateway",
            "--gateway-adapter",
            "slack",
            "--gateway-target",
            "slack://ops",
            "--home",
            str(tmp_path),
            "--json",
        ],
    )
    dry_run = runner.invoke(
        app,
        [
            "live-dry-run",
            "--surface-id",
            "gateway.slack",
            "--principal-id",
            "wave74.principal.operator",
            "--objective-id",
            "wave74.objective.live",
            "--home",
            str(tmp_path),
            "--now",
            "2026-06-04T12:00:00+00:00",
            "--json",
        ],
    )

    assert configured.exit_code == 0, configured.stdout
    assert dry_run.exit_code == 0, dry_run.stdout
    configured_payload = json.loads(configured.stdout)
    dry_run_payload = json.loads(dry_run.stdout)
    assert configured_payload["decision"] == "configured"
    assert configured_payload["gateway_settings"]["configured_target_count"] == 1
    assert dry_run_payload["decision"] == "planned"
    assert dry_run_payload["profile"]["preflight_request_template"]["delivery_target"] == "slack://ops"
    assert dry_run_payload["network_opened"] is False
    assert dry_run_payload["live_production_claimed"] is False


def test_python_library_setup_apply_writes_gateway_config(tmp_path: Path) -> None:
    agent = ZeusAgent(home=tmp_path)

    configured = agent.setup_apply(
        provider_id="openrouter/qwen",
        mcp=True,
        mcp_servers=("github",),
        gateway=True,
        gateway_adapter="slack",
        gateway_target="slack://ops",
    )
    dry_run = agent.live_dry_run(
        surface_id="gateway.slack",
        principal_id="wave74.principal.operator",
        objective_id="wave74.objective.live",
        now=_now(),
    )

    assert configured["decision"] == "configured"
    assert configured["gateway_settings"]["configured_target_count"] == 1
    assert dry_run["profile"]["preflight_request_template"]["delivery_target"] == "slack://ops"
    assert dry_run["external_delivery_opened"] is False
    assert dry_run["live_production_claimed"] is False


def _now() -> datetime:
    return datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
