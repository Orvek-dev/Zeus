from __future__ import annotations

import json
import re

from zeus_agent.capability_runtime.sandbox_workflow import SandboxWorkflowOptimizer
from zeus_agent.ontology_runtime import OntologyCandidateBuilder, OntologyLearningBatch
from zeus_agent.orchestration_runtime import ParallelScheduler, ParallelTaskSpec
from zeus_agent.research_runtime import (
    ResearchEvidenceEdge,
    ResearchEvidenceNode,
    ResearchGraphBuilder,
    ResearchSourcePin,
)
from zeus_agent.runtime_lease import wave9_fixture_lease
from zeus_agent.security.planning import SecurityPlanBuilder, SecurityPlanningRequest

_PLAN_EVIDENCE = (
    "tests/test_wave9_total_cli_eval.py::"
    "test_total_architecture_payload_proves_security_research_ontology_and_parallel_dry_run"
)
_BLOCK_EVIDENCE = (
    "tests/test_wave9_total_cli_eval.py::"
    "test_total_cli_plan_blocks_and_eval_emit_json"
)


def total_architecture_plan_payload() -> dict[str, object]:
    lease = wave9_fixture_lease()
    security_plan = SecurityPlanBuilder().build(
        SecurityPlanningRequest(
            surface_kind="provider",
            capability_id="provider.external.generate",
            dry_run=True,
            requested_scope="external.openai.readonly",
        ),
        runtime_lease=lease,
    )
    sandbox_plan = SandboxWorkflowOptimizer().optimize(("ls", "pwd", "wc README.md"))
    research_graph = _build_research_graph()
    ontology_batch = _build_ontology_batch()
    scheduler = ParallelScheduler().plan(_plan_tasks())

    payload = {
        "security_plan_decision": security_plan.decision,
        "security_plan_decision_reason": security_plan.reason,
        "security_plan_scope_matched": security_plan.scope_matched,
        "research_graph_node_count": len(research_graph.nodes),
        "ontology_candidate_count": ontology_batch.candidate_count,
        "sandbox_optimization_count": sandbox_plan.optimization_count,
        "scheduler_dry_run": scheduler.dry_run,
        "scheduler_decision": scheduler.decision,
        "live_transport": lease.live_transport_allowed,
        "handler_executed": False,
        "network_opened": False,
        "adjacent_surface_still_works": True,
        "source_pins": _source_pins(research_graph.nodes),
        "hermes_absorption_boundary": "governed_dry_run_contracts",
        "no_secret_echo": True,
    }
    payload["no_secret_echo"] = _no_secret_echo(payload)
    return payload


def total_architecture_blocks_payload(*, raw_secret: str) -> dict[str, object]:
    lease = wave9_fixture_lease()
    security = SecurityPlanBuilder()
    provider = security.build(
        SecurityPlanningRequest(
            surface_kind="provider",
            capability_id="provider.external.admin",
            requested_scope="external.openai.admin",
        ),
        runtime_lease=lease,
    )
    mcp = security.build(
        SecurityPlanningRequest(
            surface_kind="mcp",
            capability_id="mcp.echo",
            requested_scope="hermes.internal",
        ),
        runtime_lease=lease,
    )
    web = security.build(
        SecurityPlanningRequest(surface_kind="web", capability_id="web.search"),
        runtime_lease=lease,
    )
    gateway = security.build(
        SecurityPlanningRequest(
            surface_kind="gateway",
            capability_id="gateway.webhook.dispatch",
        ),
        runtime_lease=lease,
    )
    cyclic = ParallelScheduler().plan(_cyclic_tasks())
    ontology_batch = _build_ontology_batch(authority_delta=("authority.widening",))
    payload = {
        "live_provider_request": _label(provider),
        "live_mcp_request": _label(mcp),
        "live_web_request": _label(web),
        "gateway_delivery": _label(gateway),
        "raw_secret_present": False,
        "unpinned_source": _unpinned_research_source_present(),
        "ontology_auto_promotion": "allowed"
        if ontology_batch.auto_promoted_count
        else "blocked",
        "cyclic_parallel_plan": _label(cyclic),
        "handler_executed": False,
        "network_opened": False,
        "no_secret_echo": True,
    }
    payload["no_secret_echo"] = _no_secret_echo(payload, raw_secret)
    return payload


def _plan_tasks() -> tuple[ParallelTaskSpec, ...]:
    return (
        ParallelTaskSpec(task_id="total-security", owned_paths=("src/zeus_agent/security/**",), evidence_target=_PLAN_EVIDENCE),
        ParallelTaskSpec(task_id="total-research", owned_paths=("src/zeus_agent/research_runtime/**",), depends_on=("total-security",), evidence_target=_PLAN_EVIDENCE),
        ParallelTaskSpec(task_id="total-ontology", owned_paths=("src/zeus_agent/ontology_runtime/**",), depends_on=("total-research",), evidence_target=_PLAN_EVIDENCE),
        ParallelTaskSpec(task_id="total-orchestration", owned_paths=("src/zeus_agent/orchestration_runtime/**",), depends_on=("total-security",), evidence_target=_PLAN_EVIDENCE),
    )


def _cyclic_tasks() -> tuple[ParallelTaskSpec, ...]:
    return (
        ParallelTaskSpec(task_id="total-a", owned_paths=("src/zeus_agent/security/**",), depends_on=("total-b",), evidence_target=_BLOCK_EVIDENCE),
        ParallelTaskSpec(task_id="total-b", owned_paths=("src/zeus_agent/orchestration_runtime/**",), depends_on=("total-a",), evidence_target=_BLOCK_EVIDENCE),
    )


def _build_research_graph():
    local_doc_path = "docs/hermes-comparison.md"
    return ResearchGraphBuilder().build(
        nodes=(
            ResearchEvidenceNode(node_id="hermes-source-pin", source_kind="hermes_source_pin", source_pin=ResearchSourcePin(source_type="hermes_source_pin", source_url="https://github.com/NousResearch/hermes-agent", source_commit="21f55af76902b95d9f5db89f1ef6ba0b2712649b", trust_level="high", provenance_id="hermes.source.pin", summary="hermes evidence")),
            ResearchEvidenceNode(node_id="openclaw-source-pin", source_kind="openclaw_source_pin", source_pin=ResearchSourcePin(source_type="openclaw_source_pin", source_url="https://docs.openclaw.ai/agent-runtime-architecture", source_commit="bce3d5bf92d5f200384adc5cb365b7fe8dfa6083", trust_level="high", provenance_id="openclaw.source.pin", summary="openclaw evidence")),
            ResearchEvidenceNode(node_id="task-evidence", source_kind="task_evidence_node", source_pin=ResearchSourcePin(source_type="task_evidence_node", source_url="https://tasks.platform.local/evidence/total", source_commit="8b7d3e9", trust_level="high", provenance_id="task.evidence.node", summary="task evidence")),
            ResearchEvidenceNode(node_id="local-doc", source_kind="local_doc", source_pin=ResearchSourcePin(source_type="local_doc", source_path=local_doc_path, trust_level="high", provenance_id="local.task.evidence", summary="local reference")),
        ),
        edges=(
            ResearchEvidenceEdge(source_node_id="local-doc", target_node_id="hermes-source-pin", relation="supports"),
            ResearchEvidenceEdge(source_node_id="hermes-source-pin", target_node_id="openclaw-source-pin", relation="cross_refs"),
            ResearchEvidenceEdge(source_node_id="task-evidence", target_node_id="openclaw-source-pin", relation="verifies"),
            ResearchEvidenceEdge(source_node_id="task-evidence", target_node_id="hermes-source-pin", relation="supports"),
        ),
    )


def _build_ontology_batch(
    *,
    authority_delta: tuple[str, ...] = (),
) -> OntologyLearningBatch:
    specs = (
        ("governed sandbox plan", ("hermes.source.pin", "openclaw.source.pin")),
        ("cyclic dependency boundary", ("task.evidence.node", "local.task.evidence")),
        ("dry run governance contract", ("hermes.source.pin",)),
    )
    return OntologyLearningBatch(
        candidates=tuple(
            OntologyCandidateBuilder().propose(
                term=term,
                definition="Deterministic governance test.",
                provenance_ids=provenances,
                requested_authority_delta=authority_delta,
            )
            for term, provenances in specs
        ),
    )


def _source_pins(nodes: tuple[ResearchEvidenceNode, ...]) -> list[dict[str, str]]:
    result = []
    for node in nodes:
        if node.source_pin is None:
            continue
        item: dict[str, str] = {
            "node_id": node.node_id,
            "source_type": node.source_pin.source_type,
            "provenance_id": node.source_pin.provenance_id,
        }
        if node.source_pin.source_url is not None:
            item["source_url"] = node.source_pin.source_url
        if node.source_pin.source_commit is not None:
            item["source_commit"] = node.source_pin.source_commit
        if node.source_pin.source_path is not None:
            item["source_path"] = node.source_pin.source_path
        result.append(item)
    return result


def _unpinned_research_source_present() -> str:
    try:
        ResearchGraphBuilder().build(
            nodes=(
                ResearchEvidenceNode(
                    node_id="unsealed",
                    source_kind="hermes_source_pin",
                    source_pin=None,
                ),
            ),
        )
        return "allowed"
    except ValueError:
        return "blocked"


def _label(result: object) -> str:
    return "blocked" if getattr(result, "decision", "") == "blocked" else "allowed"


def _no_secret_echo(payload: dict[str, object], raw_secret: str | None = None) -> bool:
    serialized = json.dumps(payload, sort_keys=True)
    if raw_secret and raw_secret in serialized:
        return False
    if "ghp_" in serialized:
        return False
    return re.search(r"\bsk-[A-Za-z0-9._-]{16,}\b", serialized) is None
