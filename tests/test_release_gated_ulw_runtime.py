from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v060_live_spine_reports_provider_mcp_and_release_gate_ready() -> None:
    result = build_release_gated_ulw_status(target_version="v0.6.0")

    assert result.decision == "report"
    assert result.target_version == "v0.6.0"
    assert result.release_stage == "live_spine"
    assert result.live_spine_contract_available is True
    assert result.provider_loopback_contract_available is True
    assert result.mcp_loopback_contract_available is True
    assert result.provider_loopback_ready is False
    assert result.mcp_loopback_ready is False
    assert result.approval_lease_required is True
    assert result.release_gate_ready is False
    assert "manual_qa_evidence_captured" in result.required_checkpoint_evidence
    assert result.next_version == "v0.7.0"
    assert result.no_secret_echo is True


def test_release_gated_ulw_redacts_raw_secret_marker() -> None:
    result = build_release_gated_ulw_status(
        target_version="v0.6.0",
        raw_secret_marker_detected=True,
    )
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["raw_secret_marker_detected"] is True
    assert payload["no_secret_echo"] is True
    assert "sk-v060-secret" not in serialized


def test_release_gated_ulw_blocks_unknown_target_version() -> None:
    result = build_release_gated_ulw_status(target_version="v9.9.9")

    assert result.decision == "blocked"
    assert result.release_gate_ready is False
    assert "unknown_target_version" in result.blocked_reasons


def test_release_gated_ulw_blocks_future_release_until_current_checkpoint_closes() -> None:
    result = build_release_gated_ulw_status(target_version="v0.9.0")

    assert result.decision == "blocked"
    assert result.release_stage == "memory_ontology"
    assert result.release_gate_ready is False
    assert "prior_release_checkpoint_required" in result.blocked_reasons


def test_v070_tool_limbs_reports_governed_tool_contract() -> None:
    result = build_release_gated_ulw_status(target_version="v0.7.0")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v0.7.0"
    assert payload["release_stage"] == "tool_limbs"
    assert payload["tool_limbs_contract_available"] is True
    assert payload["native_tool_catalog_contract_available"] is True
    assert payload["mcp_tool_discovery_contract_available"] is True
    assert payload["api_connector_contract_available"] is True
    assert payload["tool_include_exclude_required"] is True
    assert payload["tool_approval_lease_required"] is True
    assert payload["tool_security_gate_required"] is True
    assert payload["tool_limbs_ready"] is False
    assert payload["release_gate_ready"] is False
    assert payload["next_version"] == "v0.8.0"
    assert payload["no_secret_echo"] is True


def test_release_gated_ulw_cli_json_surface() -> None:
    result = CliRunner().invoke(
        app,
        ["release-gated-ulw", "--target-version", "v0.6.0", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["target_version"] == "v0.6.0"
    assert payload["provider_loopback_contract_available"] is True
    assert payload["mcp_loopback_contract_available"] is True
    assert payload["provider_loopback_ready"] is False
    assert payload["mcp_loopback_ready"] is False
    assert payload["approval_lease_required"] is True
    assert payload["release_gate_ready"] is False
    assert payload["no_secret_echo"] is True


def test_release_gated_ulw_cli_accepts_secret_marker_without_raw_note() -> None:
    result = CliRunner().invoke(
        app,
        [
            "release-gated-ulw",
            "--target-version",
            "v0.6.0",
            "--raw-secret-marker-detected",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["raw_secret_marker_detected"] is True
    assert payload["no_secret_echo"] is True
    assert "raw_note" not in payload


def test_release_gated_ulw_cli_does_not_expose_raw_note_option() -> None:
    result = CliRunner().invoke(app, ["release-gated-ulw", "--help"])

    assert result.exit_code == 0
    assert "--raw-note" not in result.stdout


def test_release_gated_ulw_cli_sanitizes_secret_like_target_version() -> None:
    result = CliRunner().invoke(
        app,
        ["release-gated-ulw", "--target-version", "sk-v060-secret", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    serialized = json.dumps(payload, sort_keys=True).lower()
    assert payload["decision"] == "blocked"
    assert payload["target_version"] == "unknown"
    assert "unknown_target_version" in payload["blocked_reasons"]
    assert payload["no_secret_echo"] is True
    assert "sk-v060-secret" not in serialized
