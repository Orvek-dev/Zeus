from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from zeus_agent import ZeusAgent
from zeus_agent.memory_graph_runtime import MemoryGraphStore
from zeus_agent.ontology_cockpit_runtime import OntologyCockpitRuntime


def test_ontology_cockpit_reports_llm_wiki_candidates_without_promotion(tmp_path: Path) -> None:
    result = OntologyCockpitRuntime(tmp_path).build()

    assert result.decision == "report"
    assert result.candidate_count == 2
    assert result.proposed_candidate_count == 1
    assert result.blocked_candidate_count == 1
    assert result.promoted_candidate_count == 0
    assert result.selected_candidate is None
    assert "zeus ontology --candidate-id objective-contract --json" in result.recommended_next_commands
    assert result.memory_store_local is True
    assert result.wiki_page_update_written is False
    assert result.ontology_term_promoted is False
    assert result.active_rule_written is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_ontology_cockpit_inspects_candidate_with_local_wiki_page(tmp_path: Path) -> None:
    MemoryGraphStore(tmp_path).propose_fact(
        subject="objective_contract",
        predicate="definition",
        object_text="Goal, authority, evidence, and stop-condition contract.",
        provenance_id="evidence-wave53-objective",
    )

    result = OntologyCockpitRuntime(tmp_path).build(candidate_id="objective-contract")

    assert result.decision == "report"
    assert result.selected_candidate is not None
    assert result.selected_candidate["candidate_id"] == "objective-contract"
    assert result.selected_candidate["candidate_status"] == "proposed_not_promoted"
    assert result.selected_candidate["promoted"] is False
    assert result.selected_candidate["wiki_subject"] == "objective_contract"
    assert result.selected_candidate["wiki_page"]["fact_count"] == 1
    assert "definition" in result.selected_candidate["wiki_page"]["body"]


def test_ontology_cockpit_blocks_unsafe_rule_promotion_without_secret_echo(tmp_path: Path) -> None:
    raw_secret = "sk-" + "wave53-secret"
    result = OntologyCockpitRuntime(tmp_path).build(candidate_id="unsafe-rule-promotion")
    serialized = json.dumps(result.to_payload(), sort_keys=True)

    assert result.decision == "report"
    assert result.selected_candidate is not None
    assert result.selected_candidate["candidate_status"] == "blocked"
    assert "rule_promotion_requested" in result.selected_candidate["blocked_reasons"]
    assert "team_rule_promotion_requested" in result.selected_candidate["blocked_reasons"]
    assert raw_secret not in serialized
    assert result.no_secret_echo is True
    assert result.active_rule_written is False
    assert result.network_opened is False


def test_ontology_cockpit_blocks_unknown_candidate_inspection(tmp_path: Path) -> None:
    result = OntologyCockpitRuntime(tmp_path).build(candidate_id="unknown")

    assert result.decision == "blocked"
    assert result.selected_candidate is None
    assert result.blocked_reasons == ("unknown_ontology_candidate",)
    assert result.ontology_term_promoted is False
    assert result.live_production_claimed is False


def test_cli_exposes_ontology_cockpit_inspection(tmp_path: Path) -> None:
    MemoryGraphStore(tmp_path).propose_fact(
        subject="objective_contract",
        predicate="definition",
        object_text="Goal, authority, evidence, and stop-condition contract.",
        provenance_id="evidence-wave53-cli",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "ontology",
            "--home",
            str(tmp_path),
            "--candidate-id",
            "objective-contract",
            "--json",
        ],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["decision"] == "report"
    assert payload["selected_candidate"]["candidate_id"] == "objective-contract"
    assert payload["selected_candidate"]["wiki_page"]["fact_count"] == 1
    assert payload["ontology_term_promoted"] is False


def test_python_library_exposes_ontology_cockpit(tmp_path: Path) -> None:
    payload = ZeusAgent(home=tmp_path).ontology_status(candidate_id="unsafe-rule-promotion")

    assert payload["decision"] == "report"
    assert payload["selected_candidate"]["candidate_id"] == "unsafe-rule-promotion"
    assert payload["selected_candidate"]["candidate_status"] == "blocked"
    assert payload["live_production_claimed"] is False
