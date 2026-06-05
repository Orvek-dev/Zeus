from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime
from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyRuntime
from zeus_agent.live_research_workflow_external_preflight_runtime import (
    LiveResearchWorkflowExternalPreflightRuntime,
)
from tests.test_wave141_live_research_external_transport import _research_policy
from tests.test_wave177_live_research_workflow_loopback_executor import _ready_handoff


def test_live_cockpit_reports_research_workflow_external_preflight() -> None:
    preflight = _ready_external_preflight()

    result = LiveCockpitRuntime().build(research_workflow_external_preflight=preflight)

    assert result.decision == "report"
    assert result.research_workflow_external_preflight == preflight
    assert result.research_workflow_external_preflight_decision == "external_preflight_ready"
    assert result.research_workflow_external_preflight_ready is True
    assert result.research_workflow_external_preflight_preflight_id == preflight.preflight_id
    assert result.research_workflow_external_preflight_external_transport_allowed is True
    assert result.research_workflow_external_preflight_live_transport_enabled is False
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False
    assert "zeus live-research-workflow-external-preflight --json" in result.recommended_next_commands


def test_live_cockpit_blocks_blocked_research_workflow_external_preflight() -> None:
    handoff = _ready_handoff("external-cockpit-blocked")
    policy = LiveResearchActivationPolicyRuntime().plan(
        source_id="github",
        query="parallel coding workflow",
        live_search_requested=True,
        source_pin_ref="source-pin://research/github",
    )
    blocked = LiveResearchWorkflowExternalPreflightRuntime().build(
        handoff=handoff,
        policy=policy,
        preflight_ref="research-workflow-external-preflight://wave184/blocked",
        external_execution_ref="research-external://wave184/blocked",
        operator_approval_ref="",
        evidence_ref="",
    )

    result = LiveCockpitRuntime().build(research_workflow_external_preflight=blocked)

    assert result.decision == "blocked"
    assert (
        "research-workflow-external-preflight:"
        "research_workflow_external_policy_not_ready"
    ) in result.blocked_reasons
    assert result.research_workflow_external_preflight_ready is False
    assert result.network_opened is False


def test_live_cockpit_external_preflight_cli_and_library_surface_match() -> None:
    preflight = _ready_external_preflight()
    env = {**os.environ, "PYTHONPATH": "src"}

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live",
            "--research-workflow-external-preflight-json",
            preflight.model_dump_json(),
            "--json",
        ],
        cwd=".",
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    cli_payload = json.loads(proc.stdout)
    library_payload = ZeusAgent().live_status(
        research_workflow_external_preflight=preflight.to_payload(),
    )
    assert cli_payload == library_payload
    assert cli_payload["research_workflow_external_preflight_decision"] == "external_preflight_ready"
    assert cli_payload["network_opened"] is False


def _ready_external_preflight():
    handoff = _ready_handoff("external-cockpit-ready")
    policy = _research_policy()
    return LiveResearchWorkflowExternalPreflightRuntime().build(
        handoff=handoff,
        policy=policy,
        preflight_ref="research-workflow-external-preflight://wave184/ready",
        external_execution_ref="research-external://wave184/ready",
        operator_approval_ref=policy.approval_ref or "",
        evidence_ref="evidence://wave184/ready",
    )
