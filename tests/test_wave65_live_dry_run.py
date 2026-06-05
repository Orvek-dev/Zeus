from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from zeus_agent import ZeusAgent
from zeus_agent.live_dry_run_runtime import LiveDryRunRuntime


def test_live_dry_run_composes_provider_profile_to_execute_plan_chain() -> None:
    result = LiveDryRunRuntime().run(
        surface_id="provider.external.openai",
        principal_id="wave65.principal.operator",
        objective_id="wave65.objective.live",
        now=_now(),
    )

    assert result.decision == "planned"
    assert result.profile.decision == "profile"
    assert result.approval_receipt.decision == "recorded"
    assert result.preflight.decision == "preflight_ready"
    assert result.handoff.decision == "handoff_ready"
    assert result.execute_plan.decision == "planned"
    assert result.execution_allowed is False
    assert result.network_opened is False
    assert result.handler_executed is False
    assert result.external_delivery_opened is False
    assert result.live_production_claimed is False


def test_live_dry_run_composes_gateway_allowlist_chain() -> None:
    result = LiveDryRunRuntime().run(
        surface_id="gateway.slack",
        principal_id="wave65.principal.operator",
        objective_id="wave65.objective.live",
        delivery_target="slack://ops",
        allowlisted_delivery_targets=("slack://ops",),
        now=_now(),
    )

    assert result.decision == "planned"
    assert result.profile.surface_kind == "gateway"
    assert result.preflight.decision == "preflight_ready"
    assert result.handoff.decision == "handoff_ready"
    assert result.execute_plan.decision == "planned"
    assert result.live_production_claimed is False


def test_live_dry_run_blocks_live_execution_request() -> None:
    result = LiveDryRunRuntime().run(
        surface_id="provider.external.openai",
        principal_id="wave65.principal.operator",
        objective_id="wave65.objective.live",
        execute_live=True,
        now=_now(),
    )

    assert result.decision == "blocked"
    assert "execute_plan:live_execution_requires_external_operator" in result.blocked_reasons
    assert result.execute_plan.decision == "blocked"
    assert result.execution_allowed is False
    assert result.network_opened is False


def test_live_dry_run_blocks_unknown_surface_profile() -> None:
    result = LiveDryRunRuntime().run(
        surface_id="unknown.surface",
        principal_id="wave65.principal.operator",
        objective_id="wave65.objective.live",
        now=_now(),
    )

    assert result.decision == "blocked"
    assert "profile:unknown_live_surface_profile" in result.blocked_reasons
    assert result.execution_allowed is False
    assert result.live_production_claimed is False


def test_live_dry_run_redacts_secret_like_inputs() -> None:
    raw_secret = "sk-" + "wave65-secret"
    result = LiveDryRunRuntime().run(
        surface_id="provider.external.openai",
        principal_id="operator {0}".format(raw_secret),
        objective_id="wave65.objective.live",
        now=_now(),
    )
    serialized = result.model_dump_json()

    assert result.decision == "blocked"
    assert "profile:secret_like_profile_field" in result.blocked_reasons
    assert raw_secret not in serialized
    assert "sk-...redacted" in serialized
    assert result.no_secret_echo is True


def test_cli_exposes_live_dry_run_chain() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live-dry-run",
            "--surface-id",
            "provider.external.openai",
            "--principal-id",
            "wave65.principal.operator",
            "--objective-id",
            "wave65.objective.live",
            "--now",
            "2026-06-04T12:00:00+00:00",
            "--json",
        ],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["decision"] == "planned"
    assert payload["preflight"]["decision"] == "preflight_ready"
    assert payload["execute_plan"]["decision"] == "planned"
    assert payload["execution_allowed"] is False
    assert payload["live_production_claimed"] is False


def test_python_library_exposes_live_dry_run_chain() -> None:
    payload = ZeusAgent().live_dry_run(
        surface_id="mcp.catalog",
        principal_id="wave65.principal.operator",
        objective_id="wave65.objective.live",
        now=_now(),
    )

    assert payload["decision"] == "planned"
    assert payload["profile"]["surface_kind"] == "mcp"
    assert payload["preflight"]["decision"] == "preflight_ready"
    assert payload["execute_plan"]["execution_allowed"] is False


def _now() -> datetime:
    return datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
