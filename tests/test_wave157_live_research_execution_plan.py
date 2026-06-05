from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyRuntime
from zeus_agent.live_research_execution_plan_runtime import LiveResearchExecutionPlanRuntime
from zeus_agent.live_research_source_config_runtime import LiveResearchSourceConfigRuntime


def test_execution_plan_binds_configured_source_to_activation_policy() -> None:
    config = LiveResearchSourceConfigRuntime().configure(adapter_id="github")
    policy = _policy("github")

    result = LiveResearchExecutionPlanRuntime().plan(
        source_config=config,
        policy=policy,
        execution_ref="live-research-execution://wave157/github",
    )

    assert result.decision == "planned"
    assert result.adapter_id == "github"
    assert result.source_id == "github"
    assert result.source_config_bound is True
    assert result.activation_policy_bound is True
    assert result.endpoint_bound is True
    assert result.live_search_allowed is True
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_execution_plan_blocks_source_mismatch_and_unplanned_policy() -> None:
    config = LiveResearchSourceConfigRuntime().configure(adapter_id="github")
    mismatch = LiveResearchExecutionPlanRuntime().plan(
        source_config=config,
        policy=_policy("web"),
        execution_ref="live-research-execution://wave157/mismatch",
    )
    not_live = LiveResearchExecutionPlanRuntime().plan(
        source_config=config,
        policy=LiveResearchActivationPolicyRuntime().plan(source_id="github", query="workflow"),
        execution_ref="live-research-execution://wave157/not-live",
    )

    assert mismatch.decision == "blocked"
    assert "live_research_source_mismatch" in mismatch.blocked_reasons
    assert not_live.decision == "blocked"
    assert "live_research_activation_not_planned" in not_live.blocked_reasons
    assert mismatch.network_opened is False


def test_execution_plan_blocks_blocked_source_config() -> None:
    config = LiveResearchSourceConfigRuntime().configure(adapter_id="web")
    result = LiveResearchExecutionPlanRuntime().plan(
        source_config=config,
        policy=_policy("web"),
        execution_ref="live-research-execution://wave157/blocked-config",
    )

    assert result.decision == "blocked"
    assert "live_research_source_config_not_configured" in result.blocked_reasons
    assert result.endpoint_bound is False


def test_execution_plan_cli_and_library_surface_match() -> None:
    config = LiveResearchSourceConfigRuntime().configure(adapter_id="web", endpoint="https://search.example.dev/query")
    policy = _policy("web")
    env = {**os.environ, "PYTHONPATH": "src"}

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live-research-execution-plan",
            "--source-config-json",
            config.model_dump_json(),
            "--policy-json",
            policy.model_dump_json(),
            "--execution-ref",
            "live-research-execution://wave157/web",
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
    library_payload = ZeusAgent().live_research_execution_plan(
        source_config=config.to_payload(),
        policy=policy.to_payload(),
        execution_ref="live-research-execution://wave157/web",
    )
    assert cli_payload == library_payload


def _policy(source_id: str):
    return LiveResearchActivationPolicyRuntime().plan(
        source_id=source_id,
        query="parallel coding workflow",
        live_search_requested=True,
        approval_ref=f"approval://research/{source_id}",
        source_pin_ref=f"source-pin://research/{source_id}",
        max_results=5,
        rate_limit_per_minute=30,
    )
