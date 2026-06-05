from __future__ import annotations

import json

from zeus_agent.rc_closeout_runtime import build_rc_source_metrics


def test_rc_source_metrics_reports_current_platform_scale() -> None:
    result = build_rc_source_metrics()

    assert result.decision == "report"
    assert result.python_file_count >= 700
    assert result.python_pure_loc >= 60_000
    assert result.test_file_count >= 275
    assert result.evidence_file_count == 0
    assert result.runtime_package_count >= 150
    assert result.cli_wave_module_count >= 120
    assert result.metrics_reported is True
    assert result.hermes_parity_claimed is False
    assert result.live_production_claimed is False


def test_rc_source_metrics_exposes_targets_without_overclaiming() -> None:
    result = build_rc_source_metrics()
    target_by_id = {target.metric_id: target for target in result.targets}

    assert target_by_id["runtime_files"].actual >= 700
    assert target_by_id["python_pure_loc"].actual >= 60_000
    assert target_by_id["python_pure_loc"].target == 120_000
    assert target_by_id["test_files"].target == 500
    assert target_by_id["public_private_evidence_files"].actual == 0
    assert target_by_id["public_private_evidence_files"].target == 0
    assert target_by_id["public_private_evidence_files"].status == "met"
    assert result.target_gap_count >= 1
    assert "python_pure_loc" in result.gap_metric_ids
    assert "test_files" in result.gap_metric_ids


def test_rc_source_metrics_payload_has_no_secret_or_live_side_effects() -> None:
    result = build_rc_source_metrics()
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True
    assert "sk-wave208" not in serialized
