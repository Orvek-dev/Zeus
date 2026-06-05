from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent import ZeusAgent
from zeus_agent.live_profile_runtime import LiveProfileRuntime


def test_live_profile_composes_provider_activation_request_and_lease_template() -> None:
    result = LiveProfileRuntime().build(
        surface_id="provider.external.openai",
        principal_id="wave63.principal.operator",
        objective_id="wave63.objective.live",
    )

    assert result.decision == "profile"
    assert result.surface_kind == "provider"
    assert result.approval_id == "provider-live"
    assert result.capability_id == "provider.external.generate"
    assert result.preflight_request_template["source_pinned"] is True
    assert result.preflight_request_template["cleanup_required"] is True
    assert result.lease_template["live_transport_allowed"] is True
    assert result.lease_template["allowed_capabilities"] == ["provider.external.generate"]
    assert result.pipeline_stage_count == 4
    assert result.execution_allowed is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_live_profile_composes_gateway_allowlist_requirements() -> None:
    result = LiveProfileRuntime().build(
        surface_id="gateway.slack",
        principal_id="wave63.principal.operator",
        objective_id="wave63.objective.live",
        delivery_target="slack://ops",
        allowlisted_delivery_targets=("slack://ops", "slack://engineering"),
    )

    assert result.decision == "profile"
    assert result.surface_kind == "gateway"
    assert result.approval_id == "external-delivery"
    assert result.capability_id == "gateway.webhook.dispatch"
    assert result.preflight_request_template["delivery_target"] == "slack://ops"
    assert result.preflight_request_template["allowlisted_delivery_targets"] == [
        "slack://ops",
        "slack://engineering",
    ]
    assert result.preflight_request_template["source_pinned"] is False
    assert result.lease_template["network_hosts"] == ["gateway.local"]


def test_live_profile_composes_mcp_source_pin_requirements() -> None:
    result = LiveProfileRuntime().build(
        surface_id="mcp.catalog",
        principal_id="wave63.principal.operator",
        objective_id="wave63.objective.live",
    )

    assert result.decision == "profile"
    assert result.surface_kind == "mcp"
    assert result.approval_id == "mcp-live"
    assert result.capability_id == "mcp.echo"
    assert result.preflight_request_template["source_pinned"] is True
    assert result.preflight_request_template["mcp_description"] == "curated MCP catalog live-beta profile"
    assert result.lease_template["allowed_capabilities"] == ["mcp.echo"]


def test_live_profile_blocks_unknown_surface() -> None:
    result = LiveProfileRuntime().build(
        surface_id="unknown.surface",
        principal_id="wave63.principal.operator",
        objective_id="wave63.objective.live",
    )

    assert result.decision == "blocked"
    assert result.blocked_reasons == ("unknown_live_surface_profile",)
    assert result.execution_allowed is False
    assert result.live_production_claimed is False


def test_live_profile_redacts_secret_like_inputs() -> None:
    raw_secret = "sk-" + "wave63-secret"
    result = LiveProfileRuntime().build(
        surface_id="provider.external.openai",
        principal_id="operator {0}".format(raw_secret),
        objective_id="wave63.objective.live",
    )
    serialized = result.model_dump_json()

    assert result.decision == "blocked"
    assert "secret_like_profile_field" in result.blocked_reasons
    assert raw_secret not in serialized
    assert "sk-...redacted" in serialized
    assert result.no_secret_echo is True


def test_cli_exposes_live_profile() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live-profile",
            "--surface-id",
            "provider.external.openai",
            "--principal-id",
            "wave63.principal.operator",
            "--objective-id",
            "wave63.objective.live",
            "--json",
        ],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["decision"] == "profile"
    assert payload["surface_id"] == "provider.external.openai"
    assert payload["preflight_request_template"]["capability_id"] == "provider.external.generate"
    assert payload["execution_allowed"] is False


def test_python_library_exposes_live_profile() -> None:
    payload = ZeusAgent().live_profile(
        surface_id="gateway.slack",
        principal_id="wave63.principal.operator",
        objective_id="wave63.objective.live",
        delivery_target="slack://ops",
        allowlisted_delivery_targets=("slack://ops",),
    )

    assert payload["decision"] == "profile"
    assert payload["surface_kind"] == "gateway"
    assert payload["preflight_request_template"]["delivery_target"] == "slack://ops"
    assert payload["live_production_claimed"] is False
