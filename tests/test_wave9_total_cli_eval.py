
from __future__ import annotations

import json
import re

import pytest
from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.total_runtime import (
    total_architecture_blocks_payload,
    total_architecture_plan_payload,
)

_PRIVATE_DOC_PREFIX = "/".join(("docs", "ai"))
_RAW_SECRET_TOKEN = re.compile(r"\bsk-[A-Za-z0-9._-]{16,}\b")


def test_total_architecture_payload_proves_security_research_ontology_and_parallel_dry_run() -> None:
    payload = total_architecture_plan_payload()

    assert payload["security_plan_decision"] == "allowed"
    assert payload["security_plan_decision_reason"] in {"allowed", "dry_run"}
    assert payload["research_graph_node_count"] >= 4
    assert payload["ontology_candidate_count"] >= 3
    assert payload["sandbox_optimization_count"] >= 3
    assert payload["scheduler_decision"] == "planned"
    assert payload["scheduler_dry_run"] is True
    assert payload["live_transport"] is False
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True
    assert payload["adjacent_surface_still_works"] is True
    assert payload["hermes_absorption_boundary"] == "governed_dry_run_contracts"
    source_pins = payload["source_pins"]
    assert source_pins is not None
    pin_types = {pin["source_type"] for pin in source_pins}
    assert {"hermes_source_pin", "openclaw_source_pin"}.issubset(pin_types)

    by_type = {pin["source_type"]: pin for pin in source_pins}
    assert by_type["hermes_source_pin"]["source_commit"] == "21f55af76902b95d9f5db89f1ef6ba0b2712649b"
    assert by_type["openclaw_source_pin"]["source_url"] == "https://docs.openclaw.ai/agent-runtime-architecture"
    serialized = json.dumps(payload, sort_keys=True)
    assert _PRIVATE_DOC_PREFIX not in serialized
    assert by_type["local_doc"]["source_path"] == "docs/hermes-comparison.md"


def test_total_plan_uses_public_local_doc_path_outside_repo_root(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    payload = total_architecture_plan_payload()
    serialized = json.dumps(payload, sort_keys=True)
    by_type = {pin["source_type"]: pin for pin in payload["source_pins"]}

    assert _PRIVATE_DOC_PREFIX not in serialized
    assert by_type["local_doc"]["source_path"] == "docs/hermes-comparison.md"


def test_total_architecture_payload_exposes_reduced_zeus_core_language() -> None:
    payload = total_architecture_plan_payload()

    core_language = payload["zeus_core_language"]
    mercury_mapping = next(
        item
        for item in core_language["mappings"]
        if item["product_name"] == "Mercury"
    )
    serialized = json.dumps(payload, sort_keys=True)

    assert core_language["canonical_count"] == 12
    assert core_language["transport_product_name"] == "Mercury"
    assert core_language["technical_runtime_names_preserved"] is True
    assert core_language["hermes_name_reserved"] is True
    assert {"transport_runtime", "connector_runtime"}.issubset(
        set(mercury_mapping["technical_anchors"]),
    )
    assert _PRIVATE_DOC_PREFIX not in serialized
    assert "ghp_" not in serialized
    assert _RAW_SECRET_TOKEN.search(serialized) is None
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False


def test_total_blocks_payload_preserves_core_language_boundaries_without_secret_echo() -> None:
    raw_secret = "ghp_TEST_FIXTURE"

    payload = total_architecture_blocks_payload(raw_secret=raw_secret)
    core_language = payload["zeus_core_language"]
    forbidden_aliases = set(core_language["forbidden_aliases"])
    serialized = json.dumps(payload, sort_keys=True)

    assert {
        "Hermes Runtime",
        "Dionysus Production Mode",
        "Ares Executor",
    }.issubset(forbidden_aliases)
    assert payload["raw_secret_present"] is False
    assert payload["no_secret_echo"] is True
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False
    assert raw_secret not in serialized
    assert core_language["internal_transport_aliases"] == []
    assert not any(
        "Hermes" in alias
        for alias in core_language["internal_transport_aliases"]
    )


def test_total_cli_plan_blocks_and_eval_emit_json() -> None:
    runner = CliRunner()
    raw_secret = "ghp_TEST_FIXTURE"

    plan_result = runner.invoke(app, ["total-plan", "--json"])
    block_result = runner.invoke(
        app,
        ["total-blocks", "--secret-like", raw_secret, "--json"],
    )
    eval_result = runner.invoke(app, ["total-eval", "--json"])

    assert plan_result.exit_code == 0, plan_result.stdout
    assert block_result.exit_code == 0, block_result.stdout
    assert eval_result.exit_code == 0, eval_result.stdout

    plan_payload = json.loads(plan_result.stdout)
    block_payload = json.loads(block_result.stdout)
    eval_payload = json.loads(eval_result.stdout)

    assert plan_payload["security_plan_decision"] == "allowed"
    assert plan_payload["research_graph_node_count"] >= 4
    assert plan_payload["ontology_candidate_count"] >= 3
    assert plan_payload["sandbox_optimization_count"] >= 3
    assert plan_payload["scheduler_dry_run"] is True
    assert plan_payload["handler_executed"] is False
    assert plan_payload["network_opened"] is False

    assert block_payload["live_provider_request"] == "blocked"
    assert block_payload["live_mcp_request"] == "blocked"
    assert block_payload["live_web_request"] == "blocked"
    assert block_payload["gateway_delivery"] == "blocked"
    assert block_payload["raw_secret_present"] is False
    assert block_payload["unpinned_source"] == "blocked"
    assert block_payload["ontology_auto_promotion"] == "blocked"
    assert block_payload["cyclic_parallel_plan"] == "blocked"
    assert block_payload["handler_executed"] is False
    assert block_payload["network_opened"] is False
    assert block_payload["no_secret_echo"] is True
    assert raw_secret not in block_result.stdout

    assert eval_payload["suite"] == "total_architecture"
    assert eval_payload["total"] == 9
    assert eval_payload["passed"] == eval_payload["total"]
    assert eval_payload["failed"] == 0
    assert eval_payload["adjacent_surface_still_works"] is True
    assert {
        "core_language_mapping",
        "no_live_surface_opened",
    }.issubset({check["name"] for check in eval_payload["checks"]})
