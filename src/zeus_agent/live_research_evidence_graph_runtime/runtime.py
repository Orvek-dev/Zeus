from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_research_external_transport_runtime import LiveResearchExternalTransportResult
from zeus_agent.live_research_owned_client_transport_runtime import LiveResearchOwnedClientTransportResult
from zeus_agent.research_runtime import (
    ResearchEvidenceGraph,
    ResearchEvidenceNode,
    ResearchGraphBuilder,
    ResearchSourcePin,
)
from zeus_agent.security.credentials import redact_secret_spans

LiveResearchEvidenceGraphDecision = Literal["graph_ready", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchEvidenceGraphResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveResearchEvidenceGraphDecision
    graph_id: Optional[str]
    graph_ref: Optional[str]
    objective_id: Optional[str]
    external_execution_id: Optional[str]
    owned_client_execution_id: Optional[str] = None
    source_id: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    owned_client_result_bound: bool = False
    external_result_bound: bool = False
    graph_created: bool = False
    external_network_seen: bool = False
    graph_node_count: int = 0
    graph_edge_count: int = 0
    external_claims_pinned: bool = False
    graph_payload: Optional[dict[str, JsonValue]] = None
    network_opened: bool = False
    handler_executed: bool = False
    client_constructed: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveResearchEvidenceGraphRuntime:
    def build(
        self,
        *,
        external_result: Optional[LiveResearchExternalTransportResult] = None,
        owned_client_result: Optional[LiveResearchOwnedClientTransportResult] = None,
        graph_ref: str,
        objective_id: str,
    ) -> LiveResearchEvidenceGraphResult:
        safe_graph_ref = _safe_optional(graph_ref)
        safe_objective_id = _safe_optional(objective_id)
        resolved_external, owned_reasons = _resolve_external_result(external_result, owned_client_result)
        reasons = list(owned_reasons)
        reasons.extend(_external_reasons(resolved_external))
        if safe_graph_ref is None:
            reasons.append("graph_ref_required")
        if safe_objective_id is None:
            reasons.append("objective_id_required")
        nodes = _nodes_from_external(resolved_external)
        if not nodes:
            reasons.append("research_external_items_required")
        graph = None if reasons else _build_graph(nodes)
        if graph is None and not reasons:
            reasons.append("research_graph_build_failed")
        if reasons:
            return _result(
                external_result=resolved_external,
                owned_client_result=owned_client_result,
                graph_ref=safe_graph_ref,
                objective_id=safe_objective_id,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        return _result(
            external_result=resolved_external,
            owned_client_result=owned_client_result,
            graph_ref=safe_graph_ref,
            objective_id=safe_objective_id,
            graph=graph,
            graph_id=_graph_id(resolved_external, safe_graph_ref, safe_objective_id),
            owned_client_result_bound=owned_client_result is not None,
            external_result_bound=True,
            graph_created=True,
        )


def _resolve_external_result(
    external_result: Optional[LiveResearchExternalTransportResult],
    owned_client_result: Optional[LiveResearchOwnedClientTransportResult],
) -> tuple[Optional[LiveResearchExternalTransportResult], tuple[str, ...]]:
    if owned_client_result is None:
        return external_result, ()
    reasons = []
    if owned_client_result.decision != "executed" or not owned_client_result.research_invoked:
        reasons.append("research_owned_client_not_executed")
    if owned_client_result.external_transport_result is None:
        reasons.append("research_owned_external_result_required")
    if (
        external_result is not None
        and owned_client_result.external_transport_result is not None
        and external_result.execution_id != owned_client_result.external_transport_result.execution_id
    ):
        reasons.append("research_owned_external_mismatch")
    resolved = (
        external_result
        if external_result is not None
        else owned_client_result.external_transport_result
    )
    return resolved, tuple(dict.fromkeys(reasons))


def _external_reasons(external_result: Optional[LiveResearchExternalTransportResult]) -> tuple[str, ...]:
    if external_result is None:
        return ("research_external_result_required",)
    reasons = []
    if external_result.decision != "executed" or not external_result.research_invoked:
        reasons.append("research_external_execution_not_ready")
    if not external_result.source_pin_bound or not external_result.network_opened:
        reasons.append("research_external_evidence_incomplete")
    if external_result.redacted_response is None:
        reasons.append("research_external_response_required")
    if external_result.credential_material_accessed or external_result.raw_secret_returned:
        reasons.append("research_external_secret_leak_detected")
    if not external_result.no_secret_echo or external_result.live_production_claimed:
        reasons.append("research_external_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _nodes_from_external(
    external_result: Optional[LiveResearchExternalTransportResult],
) -> tuple[ResearchEvidenceNode, ...]:
    if external_result is None or external_result.redacted_response is None:
        return ()
    raw_items = external_result.redacted_response.get("items")
    if not isinstance(raw_items, list):
        return ()
    nodes: list[ResearchEvidenceNode] = []
    for idx, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        url = item.get("url")
        if not isinstance(title, str) or not isinstance(url, str):
            continue
        source_kind = _source_kind(external_result.source_id)
        node_id = "live.{0}.{1}".format(external_result.source_id or "research", idx)
        nodes.append(
            ResearchEvidenceNode(
                node_id=node_id,
                source_kind=source_kind,
                source_pin=ResearchSourcePin(
                    source_type=source_kind,
                    source_url=redact_secret_spans(url),
                    source_commit=external_result.execution_id or "live-research-external",
                    trust_level="medium",
                    freshness="fresh",
                    provenance_id=node_id,
                    summary=redact_secret_spans(title),
                ),
            ),
        )
    return tuple(nodes)


def _source_kind(source_id: Optional[str]) -> Literal["web_source_pin", "github_source_pin"]:
    if source_id == "github":
        return "github_source_pin"
    return "web_source_pin"


def _build_graph(nodes: tuple[ResearchEvidenceNode, ...]) -> Optional[ResearchEvidenceGraph]:
    try:
        return ResearchGraphBuilder().build(nodes=nodes)
    except ValueError:
        return None


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _graph_id(
    external_result: Optional[LiveResearchExternalTransportResult],
    graph_ref: Optional[str],
    objective_id: Optional[str],
) -> str:
    payload = {
        "execution_id": None if external_result is None else external_result.execution_id,
        "graph_ref": graph_ref,
        "objective_id": objective_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-research-graph-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    external_result: Optional[LiveResearchExternalTransportResult],
    owned_client_result: Optional[LiveResearchOwnedClientTransportResult],
    graph_ref: Optional[str],
    objective_id: Optional[str],
    blocked_reasons: tuple[str, ...] = (),
    graph: Optional[ResearchEvidenceGraph] = None,
    graph_id: Optional[str] = None,
    owned_client_result_bound: bool = False,
    external_result_bound: bool = False,
    graph_created: bool = False,
) -> LiveResearchEvidenceGraphResult:
    graph_payload = None if graph is None else graph.model_dump(mode="json")
    return LiveResearchEvidenceGraphResult(
        decision="graph_ready" if graph_created else "blocked",
        graph_id=graph_id,
        graph_ref=graph_ref,
        objective_id=objective_id,
        external_execution_id=None if external_result is None else external_result.execution_id,
        owned_client_execution_id=None if owned_client_result is None else owned_client_result.execution_id,
        source_id=None if external_result is None else external_result.source_id,
        blocked_reasons=blocked_reasons,
        owned_client_result_bound=owned_client_result_bound,
        external_result_bound=external_result_bound,
        graph_created=graph_created,
        external_network_seen=False if external_result is None else external_result.network_opened,
        graph_node_count=0 if graph is None else graph.node_count,
        graph_edge_count=0 if graph is None else graph.edge_count,
        external_claims_pinned=False if graph is None else graph.external_claims_pinned,
        graph_payload=graph_payload,
        network_opened=False,
        handler_executed=False,
        client_constructed=False,
        credential_material_accessed=False,
        raw_secret_returned=False,
        no_secret_echo=False if graph is not None and not graph.no_secret_echo else True,
        live_production_claimed=False,
    )
