from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_execution_readiness_runtime import LiveExecutionReadinessResult
from zeus_agent.live_provider_execution_runtime import LiveProviderExecutionRuntime


def test_live_provider_execution_blocks_without_ready_envelope() -> None:
    result = LiveProviderExecutionRuntime().generate(
        readiness=None,
        provider_kind="fake",
        message="summarize local state",
    )

    assert result.decision == "blocked"
    assert "execution_readiness_required" in result.blocked_reasons
    assert result.provider_invoked is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_live_provider_execution_runs_fake_provider_without_network() -> None:
    result = LiveProviderExecutionRuntime().generate(
        readiness=_provider_readiness(),
        provider_kind="fake",
        message="summarize local state",
    )

    assert result.decision == "selected"
    assert result.provider_decision == "selected"
    assert result.provider_invoked is True
    assert result.content == "fake provider dry-run response"
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.external_delivery_opened is False
    assert result.live_production_claimed is False


def test_live_provider_execution_blocks_external_provider_even_when_ready() -> None:
    result = LiveProviderExecutionRuntime().generate(
        readiness=_provider_readiness(),
        provider_kind="openai_compatible",
        message="call external provider",
    )

    assert result.decision == "blocked"
    assert "external_provider_execution_not_enabled" in result.blocked_reasons
    assert result.provider_invoked is False
    assert result.network_opened is False
    assert result.credential_material_accessed is False


def test_cli_and_python_library_live_provider_execution() -> None:
    readiness = _provider_readiness()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-provider-generate",
            "--readiness-json",
            readiness.model_dump_json(),
            "--provider-kind",
            "fake",
            "--message",
            "summarize local state",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "selected"
    assert payload["network_opened"] is False

    library_payload = ZeusAgent().live_provider_generate(
        readiness.to_payload(),
        provider_kind="fake",
        message="summarize local state",
    )
    assert library_payload["decision"] == "selected"
    assert library_payload["provider_invoked"] is True


def _provider_readiness() -> LiveExecutionReadinessResult:
    return LiveExecutionReadinessResult(
        decision="ready_for_external_operator",
        readiness_id="wave86.readiness.provider",
        execution_plan_id="live-execute-plan-wave86",
        handoff_manifest_id="live-handoff-wave86",
        surface_kind="provider",
        surface_id="provider.external.openai",
        capability_id="provider.external.generate",
        credential_bindings_ready=True,
        gateway_pairing_ready=True,
        secret_resolver_ready=True,
        operator_proof_bound=True,
        blocked_reasons=(),
        gate_summary={
            "credential_bindings_ready": True,
            "gateway_pairing_ready": True,
            "network_opened": False,
            "credential_material_accessed": False,
        },
        operator_proof_summary={
            "proof_id": "wave86.proof.operator",
            "operator_reviewed": True,
            "execution_authorized": False,
        },
        execution_allowed=False,
        authority_granted=False,
        live_transport_enabled=False,
        network_opened=False,
        handler_executed=False,
        external_delivery_opened=False,
        credential_material_accessed=False,
        live_production_claimed=False,
    )
