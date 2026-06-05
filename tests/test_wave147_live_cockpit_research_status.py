from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime
from zeus_agent.live_research_status_runtime import LiveResearchStatusRuntime
from tests.test_wave146_live_research_status import _chain


def test_live_cockpit_absorbs_research_status_without_opening_new_network(tmp_path: Path) -> None:
    research_status = _research_status(tmp_path)

    result = LiveCockpitRuntime(tmp_path).build(research_status=research_status)

    assert result.decision == "report"
    assert result.research_status is not None
    assert result.research_status.decision == "recorded"
    assert result.research_status_decision == "recorded"
    assert result.research_chain_recorded is True
    assert result.research_external_network_seen is True
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False
    assert "zeus live-research-status --json" in result.recommended_next_commands


def test_live_cockpit_blocks_when_research_status_is_blocked(tmp_path: Path) -> None:
    blocked_status = _research_status(tmp_path).model_copy(
        update={"decision": "blocked", "blocked_reasons": ("ontology_record_candidate_mismatch",)},
    )

    result = LiveCockpitRuntime(tmp_path).build(research_status=blocked_status)

    assert result.decision == "blocked"
    assert "research:ontology_record_candidate_mismatch" in result.blocked_reasons
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_cli_and_python_library_live_cockpit_research_status(tmp_path: Path) -> None:
    research_status = _research_status(tmp_path)
    completed = CliRunner().invoke(
        app,
        [
            "live",
            "--home",
            str(tmp_path),
            "--research-status-json",
            research_status.model_dump_json(),
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).live_status(
        research_status=research_status.to_payload(),
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "report"
    assert payload["research_status_decision"] == "recorded"
    assert payload["research_chain_recorded"] is True
    assert payload["network_opened"] is False
    assert library_payload["research_status_decision"] == "recorded"


def _research_status(tmp_path: Path):
    policy, external, graph, ingestion, record = _chain(tmp_path)
    return LiveResearchStatusRuntime().build(
        policy=policy,
        external_result=external,
        graph_result=graph,
        ingestion=ingestion,
        registry_record=record,
    )
