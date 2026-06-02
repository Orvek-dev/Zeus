from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator, model_validator

from zeus_agent.security.credentials import redact_secret_spans

SourceKind = Literal[
    "local_doc",
    "hermes_source_pin",
    "openclaw_source_pin",
    "task_evidence_node",
]
TrustLevel = Literal["low", "medium", "high"]


def _require_non_empty(value: str, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("{0} must be non_empty".format(field_name))
    return text


def _contains_secret_like(raw_value: str) -> bool:
    return redact_secret_spans(raw_value.strip()) != raw_value.strip()


class ResearchSourcePin(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_type: SourceKind
    trust_level: TrustLevel
    provenance_id: str
    summary: str
    source_url: Optional[str] = None
    source_path: Optional[str] = None
    source_commit: Optional[str] = None
    captured_at: Optional[datetime] = None

    @field_validator("source_type")
    @classmethod
    def _validate_source_type(cls, value: SourceKind) -> SourceKind:
        return value

    @field_validator("trust_level")
    @classmethod
    def _validate_trust_level(cls, value: TrustLevel) -> TrustLevel:
        return value

    @field_validator("provenance_id", "summary")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_non_empty(value, info.field_name)

    @field_validator("source_url", "source_path", "source_commit")
    @classmethod
    def _validate_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip()

    @model_validator(mode="after")
    def _validate_payload(self) -> "ResearchSourcePin":
        is_local = self.source_type == "local_doc"
        is_external = self.source_type in {"hermes_source_pin", "openclaw_source_pin", "task_evidence_node"}
        if is_local:
            if not self.source_path:
                raise ValueError("local_doc_requires_source_path")
            if self.source_url is not None:
                raise ValueError("local_doc_cannot_use_source_url")
        if is_external:
            if not self.source_url:
                raise ValueError("external_claim_requires_source_url")
            if not (self.source_commit or self.captured_at):
                raise ValueError("external_claim_requires_source_commit_or_captured_at")
        return self


class ResearchEvidenceNode(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    node_id: str
    source_kind: SourceKind
    source_pin: Optional[ResearchSourcePin] = None

    @field_validator("node_id")
    @classmethod
    def _validate_node_id(cls, value: str) -> str:
        return _require_non_empty(value, "node_id")


class ResearchEvidenceEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_node_id: str
    target_node_id: str
    relation: str

    @field_validator("source_node_id", "target_node_id", "relation")
    @classmethod
    def _validate_edge_fields(cls, value: str, info: ValidationInfo) -> str:
        if info.field_name in {"source_node_id", "target_node_id", "relation"}:
            return _require_non_empty(value, info.field_name)
        return value


class ResearchEvidenceGraph(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    nodes: list[ResearchEvidenceNode]
    edges: list[ResearchEvidenceEdge]
    network_opened: bool = False
    handler_executed: bool = False

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    @property
    def external_claims_pinned(self) -> bool:
        return all(
            node.source_kind == "local_doc" or node.source_pin is not None
            for node in self.nodes
        )

    @property
    def no_secret_echo(self) -> bool:
        texts: list[str] = []
        for node in self.nodes:
            if node.source_pin is None:
                texts.append(node.node_id)
                texts.append(node.source_kind)
                continue
            pin = node.source_pin
            texts.extend([pin.summary, pin.provenance_id])
            if pin.source_url is not None:
                texts.append(pin.source_url)
            if pin.source_commit is not None:
                texts.append(pin.source_commit)
            if pin.source_path is not None:
                texts.append(pin.source_path)
        texts.extend([self.node_count.__str__(), self.edge_count.__str__(), str(self.network_opened), str(self.handler_executed)])
        return not any(_contains_secret_like(text) for text in texts)
