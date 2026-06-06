from __future__ import annotations

from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v210_release_gate_reports_kernel_throughput_integration_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v2.1.0")
    payload = result.to_payload()

    assert payload["kernel_throughput_integration_available"] is True
    assert payload["broker_evidence_required"] is True
    assert payload["target_version"] == "v2.1.0"
    assert payload["release_stage"] == "kernel_throughput_integration"
    assert payload["decision"] == "report"
    assert payload["production_ready"] is False
    assert "kernel_throughput_integration_broker_evidence_manual_qa" in payload[
        "required_checkpoint_evidence"
    ]


def test_v210_release_gate_blocks_production_ready_without_broker_evidence() -> None:
    result = build_release_gated_ulw_status(target_version="v2.1.0")
    payload = result.to_payload()

    assert payload["broker_evidence_required"] is True
    assert payload["broker_evidence_recorded"] is False
    assert payload["production_ready"] is False
    assert payload["release_gate_ready"] is False
    assert "broker_evidence_required" in payload["blocked_reasons"]
