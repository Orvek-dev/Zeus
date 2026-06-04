from __future__ import annotations

import pytest

from zeus_agent.live_connection_runtime.trace import redact_live_connection_text, serialized_has_no_secret_echo
from zeus_agent.observability_runtime import (
    EvidenceMatrixRow,
    ObservabilityAuditEntry,
    ObservabilityGateReport,
    TraceSpan,
)
from zeus_agent.wave20_observability_scenarios import (
    wave20_observability_blocks_payload,
    wave20_observability_payload,
)


def test_wave20_observability_happy_path_records_all_gates_without_side_effects() -> None:
    # Given: Zeus assembles the observability/security gate package for a live-capable plan.
    payload = wave20_observability_payload()

    # Then: trace, audit, evidence, security, release, and review gates are all observable.
    assert payload["scenario_id"] == "C001"
    assert payload["observability_gate_created"] is True
    assert payload["trace_span_count"] >= 4
    assert payload["audit_log_count"] >= 4
    assert payload["evidence_matrix_rows"] >= 6
    assert payload["threat_model_gate"] == "pass"
    assert payload["secret_echo_gate"] == "pass"
    assert payload["release_no_claim_gate"] == "pass"
    assert payload["production_release_blocked"] is True
    assert payload["release_approval_evidence_id"] is None
    assert payload["independent_review_recorded"] is True
    assert payload["independent_review_evidence_id"] == "review.g007.independent-review-record"
    assert payload["manual_qa_channel_recorded"] is True
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True
    assert payload["live_production_claimed"] is False


def test_wave20_observability_blocks_missing_and_unsafe_gate_inputs() -> None:
    # Given: unsafe or incomplete observability gate inputs contain a secret-like sentinel.
    raw_secret = "sk-wave20-observability-secret"
    payload = wave20_observability_blocks_payload(raw_secret=raw_secret)

    # Then: each required gate fails closed without echoing the sentinel or side effects.
    assert payload["scenario_id"] == "C002"
    assert payload["missing_threat_model"] == "blocked"
    assert payload["missing_evidence"] == "blocked"
    assert payload["stale_evidence"] == "blocked"
    assert payload["secret_echo"] == "blocked"
    assert payload["release_claim"] == "blocked"
    assert payload["missing_independent_review"] == "blocked"
    assert payload["malformed_gate_record"] == "blocked"
    assert payload["blocked_handler_executed"] is False
    assert payload["blocked_network_opened"] is False
    assert payload["raw_secret_present"] is False
    assert payload["no_secret_echo"] is True
    assert payload["live_production_claimed"] is False
    assert raw_secret not in repr(payload)


def test_wave20_audit_entry_rejects_side_effect_claims() -> None:
    with pytest.raises(ValueError, match="side_effect_claim_not_allowed"):
        ObservabilityAuditEntry(
            audit_id="audit.wave20.side-effect",
            gate_id="secret_echo_gate",
            event="gate_checked",
            status="pass",
            message="side effect attempted",
            handler_executed=True,
        )


def test_wave20_report_does_not_pass_with_blocked_or_stale_rows() -> None:
    # Given: top-level gates claim pass while row-level trace/audit/evidence is unsafe.
    blocked_report = ObservabilityGateReport(
        scenario_id="blocked-row-regression",
        trace_spans=_trace_spans("blocked"),
        audit_log=_audit_log("blocked"),
        evidence_matrix=_evidence_rows("pass"),
        threat_model_gate="pass",
        secret_echo_gate="pass",
        release_no_claim_gate="pass",
        independent_review_recorded=True,
        independent_review_evidence_id="review.g007.regression",
        manual_qa_channel_recorded=True,
    )
    stale_report = ObservabilityGateReport(
        scenario_id="stale-row-regression",
        trace_spans=_trace_spans("pass"),
        audit_log=_audit_log("pass"),
        evidence_matrix=_evidence_rows("pass", stale=True),
        threat_model_gate="pass",
        secret_echo_gate="pass",
        release_no_claim_gate="pass",
        independent_review_recorded=True,
        independent_review_evidence_id="review.g007.regression",
        manual_qa_channel_recorded=True,
    )

    # Then: count-only top-level pass claims cannot mask blocked or stale rows.
    assert blocked_report.observability_gate_created is False
    assert stale_report.observability_gate_created is False


def test_wave20_report_requires_unique_required_gate_ids_and_review_evidence() -> None:
    # Given: reports omit a required gate id, duplicate another, or claim review without evidence.
    missing_trace_gate = (
        TraceSpan(span_id="span.1", name="one", gate_id="threat_model_gate", status="pass"),
        TraceSpan(span_id="span.2", name="two", gate_id="trace_gate", status="pass"),
        TraceSpan(span_id="span.3", name="three", gate_id="evidence_matrix_gate", status="pass"),
        TraceSpan(span_id="span.4", name="four", gate_id="evidence_matrix_gate", status="pass"),
    )
    malformed_gate_report = ObservabilityGateReport(
        scenario_id="missing-gate-id",
        trace_spans=missing_trace_gate,
        audit_log=_audit_log("pass"),
        evidence_matrix=_evidence_rows("pass"),
        threat_model_gate="pass",
        secret_echo_gate="pass",
        release_no_claim_gate="pass",
        independent_review_recorded=True,
        independent_review_evidence_id="review.g007.regression",
        manual_qa_channel_recorded=True,
    )

    # Then: required gate identity is part of the contract, not just row count.
    assert malformed_gate_report.observability_gate_created is False
    with pytest.raises(ValueError, match="independent_review_evidence_required"):
        ObservabilityGateReport(
            scenario_id="missing-review-evidence",
            trace_spans=_trace_spans("pass"),
            audit_log=_audit_log("pass"),
            evidence_matrix=_evidence_rows("pass"),
            threat_model_gate="pass",
            secret_echo_gate="pass",
            release_no_claim_gate="pass",
            independent_review_recorded=True,
            manual_qa_channel_recorded=True,
        )


def test_wave20_redacts_structured_json_style_secret_values() -> None:
    # Given: future gate messages may carry JSON/YAML/env shaped secret fields.
    raw = '{"api_key":"abc123","password": "letmein", "safe": "ok"}'
    audit = ObservabilityAuditEntry(
        audit_id="audit.wave20.structured-secret",
        gate_id="secret_echo_gate",
        event="gate_checked",
        status="pass",
        message=raw,
    )
    serialized = audit.model_dump_json()

    # Then: structured secret values are redacted and fail raw secret echo checks.
    assert "abc123" not in serialized
    assert "letmein" not in serialized
    assert redact_live_connection_text(raw) != raw
    assert serialized_has_no_secret_echo(raw) is False


def _trace_spans(status: str) -> tuple[TraceSpan, ...]:
    return (
        TraceSpan(span_id="span.1", name="one", gate_id="threat_model_gate", status=status),
        TraceSpan(span_id="span.2", name="two", gate_id="trace_gate", status=status),
        TraceSpan(span_id="span.3", name="three", gate_id="evidence_matrix_gate", status=status),
        TraceSpan(span_id="span.4", name="four", gate_id="release_no_claim_gate", status=status),
    )


def _audit_log(status: str) -> tuple[ObservabilityAuditEntry, ...]:
    return (
        ObservabilityAuditEntry(audit_id="audit.1", gate_id="threat_model_gate", event="checked", status=status, message="ok"),
        ObservabilityAuditEntry(audit_id="audit.2", gate_id="secret_echo_gate", event="checked", status=status, message="ok"),
        ObservabilityAuditEntry(audit_id="audit.3", gate_id="release_no_claim_gate", event="checked", status=status, message="ok"),
        ObservabilityAuditEntry(audit_id="audit.4", gate_id="independent_review_gate", event="checked", status=status, message="ok"),
    )


def _evidence_rows(status: str, *, stale: bool = False) -> tuple[EvidenceMatrixRow, ...]:
    return tuple(
        EvidenceMatrixRow(gate_id=gate_id, evidence_target=f"g007.{gate_id}", manual_qa_channel="script-pty", status=status, stale=stale)
        for gate_id in (
            "threat_model_gate",
            "trace_gate",
            "audit_gate",
            "secret_echo_gate",
            "release_no_claim_gate",
            "independent_review_gate",
        )
    )
