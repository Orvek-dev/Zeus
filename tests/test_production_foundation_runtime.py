from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.credential_readiness_runtime import CredentialReadinessRuntime
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.production_foundation_runtime import build_production_foundation_contract
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status
from zeus_agent.setup_runtime import setup_apply


def test_v100rc1_release_gate_reports_production_foundation_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v1.0.0-rc.1")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.0.0-rc.1"
    assert payload["release_stage"] == "production_foundation"
    assert payload["production_foundation_contract_available"] is True
    assert payload["identity_runtime_available"] is True
    assert payload["auth_runtime_available"] is True
    assert payload["approval_runtime_available"] is True
    assert payload["credential_binding_runtime_available"] is True
    assert payload["secret_resolver_runtime_available"] is True
    assert payload["audit_runtime_available"] is True
    assert payload["sandbox_policy_available"] is True
    assert payload["production_foundation_ready"] is False
    assert payload["production_ready"] is False
    assert payload["release_gate_ready"] is False
    assert "production_foundation_release_gate_manual_qa" in payload["required_checkpoint_evidence"]
    assert payload["no_secret_echo"] is True


def test_production_foundation_reports_security_controls_without_live_side_effects(tmp_path) -> None:
    result = build_production_foundation_contract(home=tmp_path, include_credentials=True)
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.0.0-rc.1"
    assert payload["objective_contract_id"] == "zeus.v1.0.0-rc.1.production_foundation"
    assert payload["production_foundation_ready"] is False
    assert payload["production_ready"] is False
    assert payload["identity_runtime_available"] is True
    assert payload["auth_runtime_available"] is True
    assert payload["approval_runtime_available"] is True
    assert payload["runtime_lease_available"] is True
    assert payload["credential_binding_runtime_available"] is True
    assert payload["secret_resolver_runtime_available"] is True
    assert payload["audit_runtime_available"] is True
    assert payload["sandbox_policy_available"] is True
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["external_delivery_opened"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["authority_widened"] is False
    assert payload["no_secret_echo"] is True
    assert payload["credential_bindings_ready"] is False
    assert payload["credential_readiness"]["credential_material_accessed"] is False
    assert payload["secret_resolver"]["decision"] == "blocked"
    assert "credential_binding_not_ready" in payload["secret_resolver"]["blocked_reasons"]
    assert payload["secret_resolver"]["material_access_allowed"] is False


def test_production_foundation_ready_requires_reference_bound_provider_secret_plan(tmp_path: Path) -> None:
    _seed_openai_reference_binding(tmp_path)

    result = build_production_foundation_contract(home=tmp_path, include_credentials=True)
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["production_foundation_ready"] is True
    assert payload["production_ready"] is False
    assert payload["credential_bindings_ready"] is True
    assert payload["secret_resolver"]["decision"] == "planned"
    assert payload["secret_resolver"]["target_endpoint"] == "api.openai.com"
    assert payload["secret_resolver"]["material_access_allowed"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True


def test_production_foundation_blocks_secret_like_operator_note_without_echo(tmp_path) -> None:
    result = build_production_foundation_contract(
        home=tmp_path,
        operator_note="token=sk-rc1-secret-value",
    )
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True).lower()

    assert payload["decision"] == "blocked"
    assert "raw_secret_marker_detected" in payload["blocked_reasons"]
    assert payload["operator_note"] == "[redacted-secret]"
    assert payload["no_secret_echo"] is True
    assert "sk-rc1-secret-value" not in serialized


@pytest.mark.parametrize(
    "operator_note",
    (
        "token: abc123",
        "password: abc123",
        "secret: abc123",
        "api_key: abc123",
    ),
)
def test_production_foundation_blocks_colon_style_secret_notes_without_echo(
    tmp_path: Path,
    operator_note: str,
) -> None:
    result = build_production_foundation_contract(home=tmp_path, operator_note=operator_note)
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True).lower()

    assert payload["decision"] == "blocked"
    assert "raw_secret_marker_detected" in payload["blocked_reasons"]
    assert payload["operator_note"] == "[redacted-secret]"
    assert payload["no_secret_echo"] is True
    assert "abc123" not in serialized


def test_production_foundation_cli_and_library_match(tmp_path) -> None:
    _seed_openai_reference_binding(tmp_path)
    cli_result = CliRunner().invoke(
        app,
        ["production-foundation", "--home", str(tmp_path), "--include-credentials", "--json"],
    )

    assert cli_result.exit_code == 0
    cli_payload = json.loads(cli_result.stdout)
    library_payload = ZeusAgent(home=tmp_path).production_foundation(include_credentials=True)

    assert cli_payload["target_version"] == library_payload["target_version"]
    assert cli_payload["objective_contract_id"] == library_payload["objective_contract_id"]
    assert cli_payload["production_foundation_ready"] is True
    assert library_payload["production_foundation_ready"] is True
    assert cli_payload["production_ready"] is False
    assert library_payload["production_ready"] is False
    assert cli_payload["no_secret_echo"] is True
    assert library_payload["no_secret_echo"] is True


def _seed_openai_reference_binding(home: Path) -> None:
    setup_apply(home=home, provider_id="openai", local=False)
    CredentialReadinessRuntime(home).bind(
        surface_kind="provider",
        surface_id="openai",
        credential_scope="external.openai.readonly",
        vault_ref="vault://zeus/external/openai/readonly",
    )
