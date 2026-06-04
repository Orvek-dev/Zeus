from __future__ import annotations

import json
from typing import Optional, Union

from pydantic import ValidationError

from zeus_agent.live_connection_runtime.trace import redact_live_connection_text
from zeus_agent.observability_runtime import (
    EvidenceMatrixRow,
    ObservabilityAuditEntry,
    ObservabilityGateReport,
    TraceSpan,
)

Wave20Value = Optional[Union[bool, int, str]]
Wave20Payload = dict[str, Wave20Value]


def wave20_observability_payload() -> Wave20Payload:
    report = _happy_report()
    return report.to_payload()


def wave20_observability_blocks_payload(raw_secret: str) -> Wave20Payload:
    safe_secret = redact_live_connection_text(raw_secret)
    payload: Wave20Payload = {
        "scenario_id": "C002",
        "missing_threat_model": _blocked_if(_unsafe_report(threat_model_gate="blocked").observability_gate_created is False),
        "missing_evidence": _blocked_if(_missing_evidence_blocked()),
        "stale_evidence": _blocked_if(_stale_evidence_blocked()),
        "secret_echo": _blocked_if(safe_secret == "[redacted-secret]"),
        "release_claim": _blocked_if(_release_claim_blocked()),
        "missing_independent_review": _blocked_if(
            _unsafe_report(independent_review_recorded=False, independent_review_evidence_id=None).observability_gate_created is False,
        ),
        "malformed_gate_record": _blocked_if(_malformed_gate_record_blocked()),
        "blocked_handler_executed": False,
        "blocked_network_opened": False,
        "raw_secret_present": False,
        "no_secret_echo": True,
        "live_production_claimed": False,
    }
    serialized = json.dumps(payload, sort_keys=True)
    if raw_secret != "" and raw_secret in serialized:
        return {**payload, "raw_secret_present": True, "no_secret_echo": False}
    return payload


def _happy_report() -> ObservabilityGateReport:
    return ObservabilityGateReport(
        scenario_id="C001",
        trace_spans=_trace_spans("pass"),
        audit_log=_audit_log("pass"),
        evidence_matrix=_evidence_matrix("pass"),
        threat_model_gate="pass",
        secret_echo_gate="pass",
        release_no_claim_gate="pass",
        independent_review_recorded=True,
        independent_review_evidence_id="review.g007.independent-review-record",
        manual_qa_channel_recorded=True,
    )


def _unsafe_report(
    *,
    threat_model_gate: str = "pass",
    secret_echo_gate: str = "pass",
    release_no_claim_gate: str = "pass",
    independent_review_recorded: bool = True,
    independent_review_evidence_id: str | None = "review.g007.independent-review-record",
    row_status: str = "pass",
    stale_evidence: bool = False,
) -> ObservabilityGateReport:
    return ObservabilityGateReport(
        scenario_id="C002",
        trace_spans=_trace_spans(row_status),
        audit_log=_audit_log(row_status),
        evidence_matrix=_evidence_matrix(row_status, stale=stale_evidence),
        threat_model_gate=threat_model_gate,
        secret_echo_gate=secret_echo_gate,
        release_no_claim_gate=release_no_claim_gate,
        independent_review_recorded=independent_review_recorded,
        independent_review_evidence_id=independent_review_evidence_id,
        manual_qa_channel_recorded=True,
    )


def _trace_spans(status: str) -> tuple[TraceSpan, ...]:
    return (
        TraceSpan(
            span_id="span.wave20.objective",
            name="objective_contract_bound",
            gate_id="threat_model_gate",
            status=status,
        ),
        TraceSpan(
            span_id="span.wave20.trace",
            parent_id="span.wave20.objective",
            name="trace_spans_recorded",
            gate_id="trace_gate",
            status=status,
        ),
        TraceSpan(
            span_id="span.wave20.evidence",
            parent_id="span.wave20.objective",
            name="evidence_matrix_bound",
            gate_id="evidence_matrix_gate",
            status=status,
        ),
        TraceSpan(
            span_id="span.wave20.release",
            parent_id="span.wave20.objective",
            name="release_no_claim_checked",
            gate_id="release_no_claim_gate",
            status=status,
        ),
    )


def _audit_log(status: str) -> tuple[ObservabilityAuditEntry, ...]:
    return (
        ObservabilityAuditEntry(
            audit_id="audit.wave20.threat_model",
            gate_id="threat_model_gate",
            event="gate_checked",
            status=status,
            message="attack surface record present",
        ),
        ObservabilityAuditEntry(
            audit_id="audit.wave20.secret_echo",
            gate_id="secret_echo_gate",
            event="gate_checked",
            status=status,
            message="secret echo scan passed",
        ),
        ObservabilityAuditEntry(
            audit_id="audit.wave20.release_claim",
            gate_id="release_no_claim_gate",
            event="gate_checked",
            status=status,
            message="production live claim absent",
        ),
        ObservabilityAuditEntry(
            audit_id="audit.wave20.review",
            gate_id="independent_review_gate",
            event="gate_checked",
            status=status,
            message="independent review recorded",
        ),
    )


def _evidence_matrix(status: str, *, stale: bool = False) -> tuple[EvidenceMatrixRow, ...]:
    return (
        _evidence("threat_model_gate", "g007.c001.threat_model", status, stale=stale),
        _evidence("trace_gate", "g007.c001.trace", status, stale=stale),
        _evidence("audit_gate", "g007.c001.audit", status, stale=stale),
        _evidence("secret_echo_gate", "g007.c001.secret_echo", status, stale=stale),
        _evidence("release_no_claim_gate", "g007.c001.release", status, stale=stale),
        _evidence("independent_review_gate", "g007.c001.review", status, stale=stale),
    )


def _evidence(gate_id: str, evidence_target: str, status: str, *, stale: bool = False) -> EvidenceMatrixRow:
    return EvidenceMatrixRow(
        gate_id=gate_id,
        evidence_target=evidence_target,
        manual_qa_channel="script-pty",
        status=status,
        stale=stale,
    )


def _missing_evidence_blocked() -> bool:
    try:
        ObservabilityGateReport(
            scenario_id="missing-evidence",
            trace_spans=_trace_spans("blocked"),
            audit_log=_audit_log("blocked"),
            evidence_matrix=(),
            threat_model_gate="pass",
            secret_echo_gate="pass",
            release_no_claim_gate="pass",
            independent_review_recorded=True,
            independent_review_evidence_id="review.g007.independent-review-record",
            manual_qa_channel_recorded=True,
        )
    except ValidationError:
        return True
    return False


def _stale_evidence_blocked() -> bool:
    report = _unsafe_report(stale_evidence=True)
    return report.observability_gate_created is False


def _release_claim_blocked() -> bool:
    try:
        ObservabilityGateReport(
            scenario_id="release-claim",
            trace_spans=_trace_spans("blocked"),
            audit_log=_audit_log("blocked"),
            evidence_matrix=_evidence_matrix("blocked"),
            threat_model_gate="pass",
            secret_echo_gate="pass",
            release_no_claim_gate="blocked",
            independent_review_recorded=True,
            independent_review_evidence_id="review.g007.independent-review-record",
            manual_qa_channel_recorded=True,
            live_production_claimed=True,
        )
    except ValidationError:
        return True
    return False


def _malformed_gate_record_blocked() -> bool:
    try:
        ObservabilityAuditEntry(
            audit_id="audit.wave20.malformed",
            gate_id="secret_echo_gate",
            event="gate_checked",
            status="pass",
            message="malformed side effect",
            network_opened=True,
        )
    except ValidationError:
        return True
    return False


def _blocked_if(blocked: bool) -> str:
    return "blocked" if blocked else "allowed"
