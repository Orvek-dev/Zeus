from __future__ import annotations

import json
from pathlib import Path

from zeus_agent.rc_closeout_runtime import RcCoverageAuditRuntime


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_rc_coverage_audit_reports_all_macro_waves_and_latest_checkpoint() -> None:
    result = RcCoverageAuditRuntime(PROJECT_ROOT).build()

    assert result.decision == "report"
    assert result.macro_wave_count == 9
    assert result.latest_micro_wave == 205
    assert result.selected_macro_wave is None
    assert result.hard_close_ready is False
    assert result.live_production_claimed is False
    assert result.network_opened is False
    assert result.no_secret_echo is True
    assert tuple(wave.wave_id for wave in result.macro_waves) == tuple(f"W{number}" for number in range(1, 10))
    assert result.macro_waves[-1].title == "Hermes-Parity Release Candidate"
    assert result.remaining_checkpoints == ("W206", "W207", "W208", "W209", "W210", "W211", "W212")


def test_rc_coverage_audit_selects_macro_wave_and_exposes_local_coverage() -> None:
    result = RcCoverageAuditRuntime(PROJECT_ROOT).build(macro_wave_id="W5")

    assert result.decision == "report"
    assert result.selected_macro_wave is not None
    assert result.selected_macro_wave.wave_id == "W5"
    assert result.selected_macro_wave.title == "MemoryGraph, Wiki, Skills"
    assert result.selected_macro_wave.source_dir_count >= 5
    assert result.selected_macro_wave.test_file_count >= 5
    assert result.selected_macro_wave.evidence_file_count == 0
    assert result.selected_macro_wave.status == "partial"


def test_rc_coverage_audit_blocks_unknown_macro_wave_without_side_effects() -> None:
    result = RcCoverageAuditRuntime(PROJECT_ROOT).build(macro_wave_id="W99")

    assert result.decision == "blocked"
    assert result.selected_macro_wave is None
    assert result.blocked_reasons == ("unknown_macro_wave",)
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_rc_coverage_audit_reports_empty_public_fixture_without_private_plan(tmp_path: Path) -> None:
    result = RcCoverageAuditRuntime(tmp_path).build()

    assert result.decision == "report"
    assert result.blocked_reasons == ()
    assert result.macro_wave_count == 9
    assert result.latest_micro_wave is None


def test_rc_coverage_audit_payload_is_json_safe() -> None:
    result = RcCoverageAuditRuntime(PROJECT_ROOT).build(macro_wave_id="W9")
    payload = result.to_payload()

    assert json.loads(json.dumps(payload))["selected_macro_wave"]["wave_id"] == "W9"
    assert "production-ready" in " ".join(payload["boundary_notes"])
