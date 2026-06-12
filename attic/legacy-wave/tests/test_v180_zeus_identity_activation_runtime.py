from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.entry_runtime import ZeusChatRuntime
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status
from zeus_agent.zeus_identity_activation_runtime import build_zeus_identity_activation_contract


def test_v180_release_gate_reports_identity_activation_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v1.8.0")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.8.0"
    assert payload["release_stage"] == "zeus_identity_live_activation_foundation"
    assert payload["zeus_identity_contract_available"] is True
    assert payload["zeus_call_name_runtime_available"] is True
    assert payload["live_activation_contract_available"] is True
    assert payload["activation_gate_available"] is True
    assert payload["lease_requirement_available"] is True
    assert payload["approval_requirement_available"] is True
    assert payload["credential_binding_requirement_available"] is True
    assert payload["sandbox_policy_requirement_available"] is True
    assert payload["audit_receipt_requirement_available"] is True
    assert payload["zeus_identity_ready"] is False
    assert payload["live_activation_foundation_ready"] is False
    assert payload["production_ready"] is False
    assert payload["next_version"] == "v1.9.0"
    assert "zeus_identity_call_name_manual_qa" in payload["required_checkpoint_evidence"]
    assert payload["no_secret_echo"] is True


def test_zeus_identity_status_uses_zeus_call_names() -> None:
    result = build_zeus_identity_activation_contract(scenario="identity-status")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.8.0"
    assert payload["objective_contract_id"] == "zeus.v1.8.0.identity_live_activation"
    assert payload["persona_id"] == "zeus"
    assert payload["display_name"] == "Zeus"
    assert payload["call_names"] == ["Zeus", "제우스"]
    assert payload["default_call_response"] == "Zeus is here."
    assert payload["korean_call_response"] == "네, 제우스입니다."
    assert payload["zeus_identity_ready"] is True
    assert payload["live_activation_foundation_ready"] is False
    assert payload["production_ready"] is False
    assert payload["no_secret_echo"] is True


def test_zeus_korean_call_smoke_returns_persona_response(tmp_path: Path) -> None:
    chat_payload = ZeusChatRuntime(tmp_path).run_turn(message="제우스야").to_payload()
    contract_payload = build_zeus_identity_activation_contract(
        scenario="korean-call-smoke",
        message="제우스야",
    ).to_payload()

    assert chat_payload["assistant_message"] == "네, 제우스입니다."
    assert contract_payload["decision"] == "report"
    assert contract_payload["call_response"] == "네, 제우스입니다."
    assert contract_payload["chat_turn_started"] is False
    assert contract_payload["authority_widened"] is False
    assert contract_payload["no_secret_echo"] is True


def test_live_activation_contract_blocks_missing_lease() -> None:
    result = build_zeus_identity_activation_contract(
        scenario="activation-check",
        objective_id="objective.v180",
        approval_id="approval.v180",
        credential_binding_ref="credential.v180",
        sandbox_policy_ref="sandbox.v180",
        audit_receipt_ref="audit.v180",
    )
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert "runtime_lease_required" in payload["blocked_reasons"]
    assert "runtime_lease" in payload["missing_activation_requirements"]
    assert payload["activation_contract_ready"] is False
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["no_secret_echo"] is True


def test_live_activation_contract_accepts_all_required_refs_without_execution() -> None:
    result = build_zeus_identity_activation_contract(
        scenario="activation-check",
        objective_id="objective.v180",
        lease_id="lease.v180",
        approval_id="approval.v180",
        credential_binding_ref="credential.v180",
        sandbox_policy_ref="sandbox.v180",
        audit_receipt_ref="audit.v180",
    )
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["activation_contract_ready"] is True
    assert payload["live_activation_foundation_ready"] is True
    assert payload["production_ready"] is False
    assert payload["network_opened"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_zeus_identity_activation_secret_marker_is_blocked_without_echo() -> None:
    result = build_zeus_identity_activation_contract(
        scenario="activation-status",
        operator_note="operator pasted sk-v180-identity-secret",
    )
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True).lower()

    assert payload["decision"] == "blocked"
    assert "raw_secret_marker_detected" in payload["blocked_reasons"]
    assert "sk-v180-identity-secret" not in serialized
    assert payload["raw_secret_returned"] is False
    assert payload["no_secret_echo"] is True


def test_zeus_identity_activation_cli_and_library_match(tmp_path: Path) -> None:
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "identity-activation-runtime",
            "--home",
            str(tmp_path),
            "--scenario",
            "identity-status",
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).identity_activation_runtime(
        scenario="identity-status",
    )

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["target_version"] == library_payload["target_version"]
    assert cli_payload["objective_contract_id"] == library_payload["objective_contract_id"]
    assert cli_payload["korean_call_response"] == "네, 제우스입니다."
    assert library_payload["zeus_identity_ready"] is True
    assert cli_payload["production_ready"] is False
    assert library_payload["production_ready"] is False
