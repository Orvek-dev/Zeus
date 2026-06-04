from __future__ import annotations

from typing import Final, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_serializer, field_validator, model_validator

from zeus_agent.live_connection_runtime.trace import (
    redact_live_connection_text,
    serialized_has_no_secret_echo,
)

GateStatus = Literal["pass", "blocked"]
_REQUIRED_TRACE_GATE_IDS: Final = (
    "threat_model_gate",
    "trace_gate",
    "evidence_matrix_gate",
    "release_no_claim_gate",
)
_REQUIRED_AUDIT_GATE_IDS: Final = (
    "threat_model_gate",
    "secret_echo_gate",
    "release_no_claim_gate",
    "independent_review_gate",
)
_REQUIRED_EVIDENCE_GATE_IDS: Final = (
    "threat_model_gate",
    "trace_gate",
    "audit_gate",
    "secret_echo_gate",
    "release_no_claim_gate",
    "independent_review_gate",
)

_MODEL_CONFIG: Final = ConfigDict(
    extra="forbid",
    frozen=True,
    hide_input_in_errors=True,
)


class TraceSpan(BaseModel):
    model_config = _MODEL_CONFIG

    span_id: str
    parent_id: Optional[str] = None
    name: str
    gate_id: str
    status: GateStatus
    handler_executed: bool = False
    network_opened: bool = False

    @field_validator("span_id", "name", "gate_id")
    @classmethod
    def _validate_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_clean_text(value, _field_name(info))

    @field_validator("parent_id")
    @classmethod
    def _validate_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _require_clean_text(value, "parent_id")

    @field_validator("handler_executed", "network_opened")
    @classmethod
    def _reject_side_effect_claim(cls, value: bool) -> bool:
        if value:
            raise ValueError("side_effect_claim_not_allowed")
        return False

    @field_serializer("span_id", "parent_id", "name", "gate_id")
    def _serialize_text(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return redact_live_connection_text(value)


class ObservabilityAuditEntry(BaseModel):
    model_config = _MODEL_CONFIG

    audit_id: str
    gate_id: str
    event: str
    status: GateStatus
    message: str
    handler_executed: bool = False
    network_opened: bool = False

    @field_validator("audit_id", "gate_id", "event", "message")
    @classmethod
    def _validate_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_clean_text(value, _field_name(info))

    @field_validator("handler_executed", "network_opened")
    @classmethod
    def _reject_side_effect_claim(cls, value: bool) -> bool:
        if value:
            raise ValueError("side_effect_claim_not_allowed")
        return False

    @field_serializer("audit_id", "gate_id", "event", "message")
    def _serialize_text(self, value: str) -> str:
        return redact_live_connection_text(value)


class EvidenceMatrixRow(BaseModel):
    model_config = _MODEL_CONFIG

    gate_id: str
    evidence_target: str
    manual_qa_channel: str
    status: GateStatus
    stale: bool = False

    @field_validator("gate_id", "evidence_target", "manual_qa_channel")
    @classmethod
    def _validate_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_clean_text(value, _field_name(info))

    @field_serializer("gate_id", "evidence_target", "manual_qa_channel")
    def _serialize_text(self, value: str) -> str:
        return redact_live_connection_text(value)


class ObservabilityGateReport(BaseModel):
    model_config = _MODEL_CONFIG

    scenario_id: str
    trace_spans: tuple[TraceSpan, ...]
    audit_log: tuple[ObservabilityAuditEntry, ...]
    evidence_matrix: tuple[EvidenceMatrixRow, ...]
    threat_model_gate: GateStatus
    secret_echo_gate: GateStatus
    release_no_claim_gate: GateStatus
    independent_review_recorded: bool
    independent_review_evidence_id: Optional[str] = None
    manual_qa_channel_recorded: bool
    handler_executed: bool = False
    network_opened: bool = False
    live_production_claimed: bool = False
    production_release_blocked: bool = True
    release_approval_evidence_id: Optional[str] = None

    @field_validator("scenario_id")
    @classmethod
    def _validate_scenario_id(cls, value: str) -> str:
        return _require_clean_text(value, "scenario_id")

    @field_validator("independent_review_evidence_id", "release_approval_evidence_id")
    @classmethod
    def _validate_optional_evidence_id(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        if value is None:
            return None
        return _require_clean_text(value, _field_name(info))

    @field_validator("trace_spans", "audit_log", "evidence_matrix")
    @classmethod
    def _require_non_empty_tuple(cls, value: tuple[object, ...], info: ValidationInfo) -> tuple[object, ...]:
        if len(value) == 0:
            raise ValueError("{0}_required".format(_field_name(info)))
        return value

    @field_validator("handler_executed", "network_opened", "live_production_claimed")
    @classmethod
    def _reject_side_effect_or_claim(cls, value: bool) -> bool:
        if value:
            raise ValueError("side_effect_or_live_claim_not_allowed")
        return False

    @model_validator(mode="after")
    def _validate_evidence_bound_claims(self) -> ObservabilityGateReport:
        if self.independent_review_recorded and self.independent_review_evidence_id is None:
            raise ValueError("independent_review_evidence_required")
        if not self.independent_review_recorded and self.independent_review_evidence_id is not None:
            raise ValueError("independent_review_evidence_without_review")
        if not self.production_release_blocked:
            raise ValueError("production_release_must_remain_blocked")
        if self.release_approval_evidence_id is not None:
            raise ValueError("release_approval_not_allowed_without_production_gate")
        return self

    @property
    def no_secret_echo(self) -> bool:
        return serialized_has_no_secret_echo(self.model_dump_json())

    @property
    def observability_gate_created(self) -> bool:
        return (
            _trace_rows_pass(self.trace_spans)
            and _audit_rows_pass(self.audit_log)
            and _evidence_rows_pass(self.evidence_matrix)
            and self.threat_model_gate == "pass"
            and self.secret_echo_gate == "pass"
            and self.release_no_claim_gate == "pass"
            and self.independent_review_recorded
            and self.independent_review_evidence_id is not None
            and self.manual_qa_channel_recorded
            and self.production_release_blocked
            and self.release_approval_evidence_id is None
            and self.no_secret_echo
        )

    def to_payload(self) -> dict[str, Union[bool, int, str, None]]:
        return {
            "scenario_id": self.scenario_id,
            "observability_gate_created": self.observability_gate_created,
            "trace_span_count": len(self.trace_spans),
            "audit_log_count": len(self.audit_log),
            "evidence_matrix_rows": len(self.evidence_matrix),
            "threat_model_gate": self.threat_model_gate,
            "secret_echo_gate": self.secret_echo_gate,
            "release_no_claim_gate": self.release_no_claim_gate,
            "independent_review_recorded": self.independent_review_recorded,
            "independent_review_evidence_id": self.independent_review_evidence_id,
            "manual_qa_channel_recorded": self.manual_qa_channel_recorded,
            "handler_executed": self.handler_executed,
            "network_opened": self.network_opened,
            "no_secret_echo": self.no_secret_echo,
            "live_production_claimed": self.live_production_claimed,
            "production_release_blocked": self.production_release_blocked,
            "release_approval_evidence_id": self.release_approval_evidence_id,
        }


def _require_clean_text(value: str, field_name: str) -> str:
    redacted = redact_live_connection_text(value.strip())
    if redacted == "":
        raise ValueError("{0}_empty".format(field_name))
    return redacted


def _field_name(info: ValidationInfo) -> str:
    if info.field_name is None:
        return "value"
    return info.field_name


def _trace_rows_pass(spans: tuple[TraceSpan, ...]) -> bool:
    gate_ids = tuple(span.gate_id for span in spans)
    return _gate_ids_exact(gate_ids, _REQUIRED_TRACE_GATE_IDS) and all(span.status == "pass" for span in spans)


def _audit_rows_pass(entries: tuple[ObservabilityAuditEntry, ...]) -> bool:
    gate_ids = tuple(entry.gate_id for entry in entries)
    return _gate_ids_exact(gate_ids, _REQUIRED_AUDIT_GATE_IDS) and all(entry.status == "pass" for entry in entries)


def _evidence_rows_pass(rows: tuple[EvidenceMatrixRow, ...]) -> bool:
    gate_ids = tuple(row.gate_id for row in rows)
    targets = tuple(row.evidence_target for row in rows)
    return (
        _gate_ids_exact(gate_ids, _REQUIRED_EVIDENCE_GATE_IDS)
        and len(set(targets)) == len(targets)
        and all(row.status == "pass" and not row.stale for row in rows)
    )


def _gate_ids_exact(actual: tuple[str, ...], required: tuple[str, ...]) -> bool:
    return len(actual) == len(required) and set(actual) == set(required)
