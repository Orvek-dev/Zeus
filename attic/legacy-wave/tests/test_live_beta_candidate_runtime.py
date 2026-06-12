from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_beta_candidate_runtime import build_live_beta_candidate_contract
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v100rc_release_gate_reports_live_beta_candidate_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v1.0.0-rc")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.0.0-rc"
    assert payload["release_stage"] == "live_beta_candidate"
    assert payload["live_beta_candidate_contract_available"] is True
    assert payload["live_readiness_contract_available"] is True
    assert payload["live_optin_smoke_contract_available"] is True
    assert payload["live_cockpit_contract_available"] is True
    assert payload["live_beta_activation_contract_available"] is True
    assert payload["rc_closeout_contract_available"] is True
    assert payload["live_beta_candidate_ready"] is False
    assert payload["production_ready"] is False
    assert "live_beta_candidate_release_gate_manual_qa" in payload["required_checkpoint_evidence"]
    assert "live_beta_candidate_secret_boundary_manual_qa" in payload["required_checkpoint_evidence"]
    assert payload["next_version"] == "v1.0.0-rc.1"
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_live_beta_candidate_contract_reports_happy_smoke_without_production_claim() -> None:
    result = build_live_beta_candidate_contract(
        include_smoke=True,
        scenario="happy",
        operator_note="release-candidate local smoke",
    )
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.0.0-rc"
    assert payload["objective_contract_id"] == "zeus.v1.0.0-rc.live_beta_candidate"
    assert payload["release_stage"] == "live_beta_candidate"
    assert payload["live_beta_candidate_ready"] is True
    assert payload["production_ready"] is False
    assert payload["smoke_included"] is True
    assert payload["smoke_decision"] == "passed"
    assert payload["surface_count"] >= 10
    assert payload["live_beta_count"] == 2
    assert payload["approval_required"] is True
    assert "runtime_lease" in payload["required_controls"]
    assert "rollback_path" in payload["required_controls"]
    assert "independent_review" in payload["required_controls"]
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["external_delivery_opened"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_live_beta_candidate_contract_blocks_adversarial_smoke() -> None:
    result = build_live_beta_candidate_contract(include_smoke=True, scenario="blocked")
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert payload["live_beta_candidate_ready"] is False
    assert payload["production_ready"] is False
    assert "provider:missing_approval" in payload["blocked_reasons"]
    assert "gateway:delivery_target_not_allowlisted" in payload["blocked_reasons"]
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_live_beta_candidate_cli_and_library_surface_match(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "live-beta-candidate",
            "--include-smoke",
            "--scenario",
            "happy",
            "--operator-note",
            "release-candidate local smoke",
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).live_beta_candidate(
        include_smoke=True,
        scenario="happy",
        operator_note="release-candidate local smoke",
    )

    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout) == library_payload
    assert library_payload["live_beta_candidate_ready"] is True
    assert library_payload["production_ready"] is False


def test_live_beta_candidate_rejects_invalid_scenario_on_cli_and_library(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "live-beta-candidate",
            "--scenario",
            "malformed",
            "--json",
        ],
    )

    assert result.exit_code == 2
    with pytest.raises(ValueError, match="scenario must be one of: happy, blocked"):
        build_live_beta_candidate_contract(scenario="malformed")
    with pytest.raises(ValueError, match="scenario must be one of: happy, blocked"):
        ZeusAgent(home=tmp_path).live_beta_candidate(scenario="malformed")


def test_live_beta_candidate_blocks_secret_like_operator_note_without_echo() -> None:
    raw_secret = "".join(("sk", "-", "v100rc-live-beta-secret"))
    result = CliRunner().invoke(
        app,
        [
            "live-beta-candidate",
            "--operator-note",
            "operator pasted token={0}".format(raw_secret),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    serialized = json.dumps(payload, sort_keys=True).lower()
    assert payload["decision"] == "blocked"
    assert payload["live_beta_candidate_ready"] is False
    assert "raw_secret_marker_detected" in payload["blocked_reasons"]
    assert payload["raw_secret_marker_detected"] is True
    assert payload["operator_note"] == "[redacted-secret]"
    assert payload["no_secret_echo"] is True
    assert raw_secret not in serialized
