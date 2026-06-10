from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from zeus_agent.capability_registry_runtime import SideEffectClass


def require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0}_empty".format(field_name))
    return normalized


class NodeKind(str, Enum):
    capability = "capability"
    llm_generic = "llm_generic"
    approval_gate = "approval_gate"
    verification = "verification"
    gap = "gap"


class WorkflowNode(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    node_id: str
    kind: NodeKind
    capability_ref: Optional[str] = None
    side_effect: SideEffectClass = SideEffectClass.none
    produces_criteria: tuple[str, ...] = ()
    verifies_criteria: tuple[str, ...] = ()
    expected_artifacts: tuple[str, ...] = ()  # verification node: files that must exist
    command: Optional[str] = None  # terminal/sandbox node: the shell command it runs
    cost_units: int = Field(default=0, ge=0)
    missing_capability: Optional[str] = None
    # Authority binding for the trust-loop action the executor builds. These let a
    # capability node request exactly the scope it needs — no broader.
    path_scope: Optional[str] = None
    network_host: Optional[str] = None
    credential_scope: Optional[str] = None
    live_network: bool = False
    mounts: tuple[str, ...] = ()
    egress_policy: str = "deny"

    @field_validator("node_id")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)

    @field_validator("capability_ref", "missing_capability", "path_scope", "network_host", "credential_scope")
    @classmethod
    def validate_optional_text(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        if value is None:
            return None
        return require_text(value, info.field_name)

    @model_validator(mode="after")
    def validate_kind_bindings(self) -> WorkflowNode:
        if self.kind is NodeKind.gap and self.missing_capability is None:
            raise ValueError("gap_node_requires_missing_capability")
        if self.kind is NodeKind.capability and self.capability_ref is None:
            raise ValueError("capability_node_requires_capability_ref")
        if self.kind is not NodeKind.capability and self.side_effect is not SideEffectClass.none:
            # Only real capability nodes carry effects; gates/verifiers/generics
            # are side-effect-free by construction.
            raise ValueError("only_capability_nodes_may_have_side_effects")
        return self


class WorkflowEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    src: str
    dst: str

    @field_validator("src", "dst")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)


class WorkflowCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    candidate_id: str
    nodes: tuple[WorkflowNode, ...] = Field(min_length=1)
    edges: tuple[WorkflowEdge, ...] = ()

    @field_validator("candidate_id")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)

    @model_validator(mode="after")
    def validate_edges_reference_nodes(self) -> WorkflowCandidate:
        node_ids = {node.node_id for node in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValueError("duplicate_node_id")
        for edge in self.edges:
            if edge.src not in node_ids or edge.dst not in node_ids:
                raise ValueError("edge_references_unknown_node")
        return self


class VerificationFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    rule: str
    detail: str
    node_id: Optional[str] = None


class CandidateVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    candidate_id: str
    ok: bool
    findings: tuple[VerificationFinding, ...]
    has_gaps: bool
    total_cost_units: int = Field(ge=0)
    covered_criteria: tuple[str, ...]


class DecisionRecord(BaseModel):
    """Why this workflow, and why not the others.

    The provenance artefact that lets a result be traced back to the choice that
    produced it. Rejected candidates keep their rejection findings.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    chosen_candidate_id: Optional[str]
    verdicts: tuple[CandidateVerdict, ...]
    rejected: tuple[str, ...]
    reason: str
