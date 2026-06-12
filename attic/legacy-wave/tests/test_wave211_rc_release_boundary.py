from __future__ import annotations

import json
from pathlib import Path

from zeus_agent.rc_closeout_runtime import build_rc_release_boundary


def test_rc_release_boundary_reports_version_and_local_artifacts_without_publication(tmp_path: Path) -> None:
    root = _release_fixture(tmp_path)
    result = build_rc_release_boundary(root=root)

    assert result.decision == "report"
    assert result.version == "0.5.0"
    assert result.local_package_candidate_present is True
    assert result.package_artifact_count >= 2
    assert result.release_candidate_ready is False
    assert result.tag_allowed is False
    assert result.push_allowed is False
    assert result.github_release_allowed is False
    assert "non_git_cwd_release_blocked" in result.release_blockers


def test_rc_release_boundary_blocks_publish_intent_from_non_git_cwd(tmp_path: Path) -> None:
    result = build_rc_release_boundary(root=_release_fixture(tmp_path), release_intent="publish")

    assert result.decision == "blocked"
    assert result.release_publication_allowed is False
    assert "publish_from_non_git_cwd_blocked" in result.blocked_reasons
    assert "project_mode_release_gate_required" in result.release_blockers


def test_rc_release_boundary_payload_has_no_live_or_secret_side_effects(tmp_path: Path) -> None:
    result = build_rc_release_boundary(root=_release_fixture(tmp_path), raw_release_note="token=wave211")
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True)

    assert result.raw_secret_marker_detected is True
    assert payload["no_secret_echo"] is True
    assert payload["network_opened"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["handler_executed"] is False
    assert payload["live_production_claimed"] is False
    assert "token=wave211" not in serialized


def _release_fixture(root: Path) -> Path:
    (root / "pyproject.toml").write_text('version = "0.5.0"\n', encoding="utf-8")
    dist = root / "dist"
    dist.mkdir()
    (dist / "zeus_agent-0.5.0-py3-none-any.whl").write_text("fixture", encoding="utf-8")
    (dist / "zeus_agent-0.5.0.tar.gz").write_text("fixture", encoding="utf-8")
    return root
