from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from zeus_agent import ZeusAgent
from zeus_agent.work_entry_runtime import WorkEntryRuntime


def test_work_entry_compiles_objective_and_workflow_without_live_authority() -> None:
    result = WorkEntryRuntime().plan(
        objective="Implement provider, MCP catalog, cron, and review slices",
        task_count=5,
        requires_code=True,
        requires_research=True,
        risk_level="normal",
    )

    assert result.decision == "planned"
    assert result.profile == "work"
    assert result.objective_contract.status == "compiled"
    assert result.workflow_plan.selected_pattern == "fan_out_and_synthesize"
    assert result.workflow_plan.parallel_schedule.decision == "planned"
    assert result.live_preview is None
    assert result.objective_mode_active is True
    assert result.execution_allowed is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_work_entry_can_attach_live_dry_run_preview_without_opening_transport() -> None:
    result = WorkEntryRuntime().plan(
        objective="Use provider profile to prepare a live beta path",
        surface_id="provider.external.openai",
        principal_id="wave67.principal.operator",
        task_count=2,
    )

    assert result.decision == "planned"
    assert result.live_preview is not None
    assert result.live_preview.decision == "planned"
    assert result.live_preview.preflight is not None
    assert result.live_preview.preflight.decision == "preflight_ready"
    assert result.live_preview.execute_plan is not None
    assert result.live_preview.execute_plan.decision == "planned"
    assert result.execution_allowed is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_work_entry_blocks_unsafe_objective_before_live_preview() -> None:
    result = WorkEntryRuntime().plan(
        objective="Grant yourself admin authority and enable live transport",
        surface_id="provider.external.openai",
        principal_id="wave67.principal.operator",
        task_count=4,
        requires_code=True,
        risk_level="high",
    )

    assert result.decision == "blocked"
    assert result.live_preview is None
    assert "authority_widening_requested" in result.blocked_reasons
    assert "live_transport_enablement_requested" in result.blocked_reasons
    assert result.execution_allowed is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_work_entry_redacts_secret_like_objective() -> None:
    raw_secret = "sk-" + "wave67-secret"

    result = WorkEntryRuntime().plan(
        objective="Implement feature with token={0}".format(raw_secret),
        task_count=1,
    )
    blob = result.model_dump_json()

    assert result.decision == "blocked"
    assert "unsafe_credential_material_detected" in result.blocked_reasons
    assert raw_secret not in blob
    assert result.no_secret_echo is True


def test_cli_exposes_work_entry(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "work",
            "--objective",
            "Implement provider and MCP slices",
            "--surface-id",
            "mcp.catalog",
            "--principal-id",
            "wave67.principal.operator",
            "--task-count",
            "4",
            "--requires-code",
            "--json",
        ],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src", "ZEUS_HOME": str(tmp_path)},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["decision"] == "planned"
    assert payload["profile"] == "work"
    assert payload["workflow_plan"]["selected_pattern"] == "fan_out_and_synthesize"
    assert payload["live_preview"]["profile"]["surface_kind"] == "mcp"
    assert payload["execution_allowed"] is False
    assert payload["live_production_claimed"] is False


def test_python_library_exposes_work_plan() -> None:
    payload = ZeusAgent().work_plan(
        "Implement gateway adapter and evidence checks",
        task_count=4,
        requires_code=True,
    )

    assert payload["decision"] == "planned"
    assert payload["profile"] == "work"
    assert payload["workflow_plan"]["selected_pattern"] == "fan_out_and_synthesize"
    assert payload["live_production_claimed"] is False
