from __future__ import annotations

import json
from pathlib import Path

from zeus_agent.rc_closeout_runtime import build_rc_security_boundary


def test_rc_security_boundary_reports_private_paths_and_release_blockers() -> None:
    result = build_rc_security_boundary(root=Path.cwd())

    assert result.decision == "report"
    assert result.private_boundary_passed is True
    assert result.private_ignore_count >= 10
    assert result.missing_private_ignores == ()
    assert result.public_release_blocked is True
    assert "project_mode_release_gate_required" in result.release_blockers
    assert "production_live_surface_evidence_required" in result.release_blockers
    assert result.security_review_required is True
    assert result.independent_review_required is True


def test_rc_security_boundary_blocks_secret_like_public_payload_without_echo() -> None:
    result = build_rc_security_boundary(root=Path.cwd(), extra_public_text="password=wave210")
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True)

    assert result.decision == "blocked"
    assert result.raw_secret_marker_detected is True
    assert "raw_secret_marker_detected" in result.blocked_reasons
    assert payload["no_secret_echo"] is True
    assert "password=wave210" not in serialized


def test_rc_security_boundary_payload_has_no_live_or_credential_side_effects() -> None:
    result = build_rc_security_boundary(root=Path.cwd())
    payload = result.to_payload()

    assert payload["credential_material_accessed"] is False
    assert payload["network_opened"] is False
    assert payload["external_delivery_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True
