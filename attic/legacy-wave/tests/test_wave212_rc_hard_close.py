from __future__ import annotations

import json
from pathlib import Path

from zeus_agent.rc_closeout_runtime import build_rc_hard_close


def test_rc_hard_close_reports_w205_w211_evidence_and_residual_blockers(tmp_path: Path) -> None:
    evidence_root = _hard_close_evidence_fixture(tmp_path)
    result = build_rc_hard_close(root=Path.cwd(), evidence_root=evidence_root)

    assert result.decision == "report"
    assert result.completed_checkpoint_count == 7
    assert result.missing_checkpoint_artifacts == ()
    assert result.hard_close_ready is True
    assert result.scope_closed_at_checkpoint == "W212"
    assert result.production_live_ready is False
    assert result.release_publication_allowed is False
    assert "production_live_surface_evidence_required" in result.residual_blockers
    assert "project_mode_release_gate_required" in result.residual_blockers


def test_rc_hard_close_blocks_missing_checkpoint_artifact(tmp_path: Path) -> None:
    result = build_rc_hard_close(root=Path.cwd(), evidence_root=tmp_path)

    assert result.decision == "blocked"
    assert result.hard_close_ready is False
    assert result.completed_checkpoint_count == 0
    assert "W205" in result.missing_checkpoint_ids
    assert "missing_required_checkpoint_artifact" in result.blocked_reasons


def test_rc_hard_close_payload_is_secret_safe_and_side_effect_free() -> None:
    result = build_rc_hard_close(root=Path.cwd(), raw_review_note="sk-wave212-secret")
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["raw_secret_marker_detected"] is True
    assert payload["no_secret_echo"] is True
    assert payload["network_opened"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["handler_executed"] is False
    assert payload["live_production_claimed"] is False
    assert "sk-wave212-secret" not in serialized


def _hard_close_evidence_fixture(root: Path) -> Path:
    for artifact_name in (
        "zeus-w205-current-docs-sync.txt",
        "zeus-w206-rc-coverage-audit.txt",
        "zeus-w207-rc-smoke-eval.txt",
        "zeus-w208-rc-source-metrics.txt",
        "zeus-w209-rc-live-opt-in-boundary.txt",
        "zeus-w210-rc-security-boundary.txt",
        "zeus-w211-rc-release-boundary.txt",
    ):
        (root / artifact_name).write_text("public fixture\n", encoding="utf-8")
    return root
