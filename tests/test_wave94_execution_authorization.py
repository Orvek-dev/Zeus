from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_execution_authorization_runtime import LiveExecutionAuthorizationRuntime
from zeus_agent.live_operator_proof_runtime import LiveOperatorProofRuntime
from zeus_agent.live_provider_request_runtime import LiveProviderRequestRuntime
from tests.test_wave91_provider_request_envelope import _provider_transport_lease, _secret_material


def test_execution_authorization_blocks_without_operator_proof(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")

    result = LiveExecutionAuthorizationRuntime().authorize(
        envelope_kind="provider",
        envelope=_provider_envelope().to_payload(),
        operator_proof=None,
        required_risks=("network", "credential_material_access", "external_provider_inference"),
    )

    assert result.decision == "blocked"
    assert "operator_proof_required" in result.blocked_reasons
    assert result.authorization_envelope_ready is False
    assert result.execution_allowed is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_execution_authorization_wraps_provider_envelope_without_execution(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")

    result = LiveExecutionAuthorizationRuntime().authorize(
        envelope_kind="provider",
        envelope=_provider_envelope().to_payload(),
        operator_proof=_operator_proof(),
        required_risks=("network", "credential_material_access", "external_provider_inference"),
    )

    assert result.decision == "authorization_ready"
    assert result.authorization_envelope_ready is True
    assert result.operator_proof_bound is True
    assert result.required_risks_acknowledged is True
    assert result.execution_allowed is False
    assert result.executor_release_granted is False
    assert result.provider_invoked is False
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.external_delivery_opened is False
    assert result.live_production_claimed is False


def test_execution_authorization_blocks_missing_risk_acknowledgement(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")

    result = LiveExecutionAuthorizationRuntime().authorize(
        envelope_kind="provider",
        envelope=_provider_envelope().to_payload(),
        operator_proof=_operator_proof(reviewed_risks=("network",)),
        required_risks=("network", "credential_material_access", "external_provider_inference"),
    )

    assert result.decision == "blocked"
    assert "required_risk_not_acknowledged" in result.blocked_reasons
    assert result.authorization_envelope_ready is False
    assert result.execution_allowed is False


def test_cli_and_python_library_execution_authorization(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")
    envelope = _provider_envelope()
    proof = _operator_proof()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-execution-authorization",
            "--envelope-kind",
            "provider",
            "--envelope-json",
            envelope.model_dump_json(),
            "--operator-proof-json",
            proof.model_dump_json(),
            "--required-risk",
            "network",
            "--required-risk",
            "credential_material_access",
            "--required-risk",
            "external_provider_inference",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "authorization_ready"
    assert payload["execution_allowed"] is False

    library_payload = ZeusAgent().live_execution_authorization(
        envelope_kind="provider",
        envelope=envelope.to_payload(),
        operator_proof=proof.to_payload(),
        required_risks=("network", "credential_material_access", "external_provider_inference"),
    )
    assert library_payload["decision"] == "authorization_ready"
    assert library_payload["executor_release_granted"] is False


def _provider_envelope():
    return LiveProviderRequestRuntime().prepare(
        transport_lease=_provider_transport_lease(),
        secret_material=_secret_material(),
        provider_kind="openai_compatible",
        model_id="gpt-test",
        endpoint="https://api.openai.local/v1/chat/completions",
        message="summarize local state",
    )


def _operator_proof(
    reviewed_risks: tuple[str, ...] = (
        "network",
        "credential_material_access",
        "external_provider_inference",
    ),
):
    return LiveOperatorProofRuntime().record(
        proof_id="wave94.proof.operator",
        operator_id="wave94.operator",
        execution_plan_id="live-execute-plan-wave94",
        proof_ref="operator-proof://wave94/review",
        reviewed_risks=reviewed_risks,
    )
