from __future__ import annotations

from typing import Iterable, Optional

from zeus_agent.research_runtime.models import (
    _contains_secret_like,
    ResearchEvidenceEdge,
    ResearchEvidenceGraph,
    ResearchEvidenceNode,
)


class ResearchGraphBuilder:
    def build(
        self,
        *,
        nodes: Iterable[ResearchEvidenceNode],
        edges: Optional[Iterable[ResearchEvidenceEdge]] = None,
    ) -> ResearchEvidenceGraph:
        node_list = list(nodes)
        edge_list = list(edges or [])
        node_ids = [node.node_id for node in node_list]

        if len(node_ids) != len(set(node_ids)):
            raise ValueError("duplicate_node_id")

        for node in node_list:
            if node.source_pin is None and node.source_kind in {"hermes_source_pin", "openclaw_source_pin", "task_evidence_node"}:
                raise ValueError("external_claims_must_be_pinned")
            if node.source_pin is None:
                if node.source_kind == "local_doc":
                    raise ValueError("local_doc_requires_source_path_pin")
                continue
            if node.source_pin.source_type != node.source_kind:
                raise ValueError("source_kind_mismatch")
            pin = node.source_pin
            if _contains_secret_like(pin.summary) or _contains_secret_like(pin.provenance_id):
                raise ValueError("secret_like_claim_fields")
            if pin.source_url is not None and _contains_secret_like(pin.source_url):
                raise ValueError("secret_like_claim_fields")
            if pin.source_path is not None and _contains_secret_like(pin.source_path):
                raise ValueError("secret_like_claim_fields")
            if pin.source_commit is not None and _contains_secret_like(pin.source_commit):
                raise ValueError("secret_like_claim_fields")

        valid_ids = set(node_ids)
        for edge in edge_list:
            if edge.source_node_id not in valid_ids or edge.target_node_id not in valid_ids:
                raise ValueError("edge_references_missing_node")

        return ResearchEvidenceGraph(
            nodes=node_list,
            edges=edge_list,
            network_opened=False,
            handler_executed=False,
        )
