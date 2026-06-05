from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_execution_authorization_runtime import LiveExecutionAuthorizationRuntime
from zeus_agent.live_executor_release_runtime import LiveExecutorReleaseRuntime
from tests.test_wave94_execution_authorization import _operator_proof, _provider_envelope


def test_executor_release_blocks_without_authorization() -> None:
    result = LiveExecutorReleaseRuntime().release(
        authorization=None,
        executor_kind="provider",
        release_ref="executor-release://wave95/provider",
        idempotency_key="wave95-provider-release-1",
    )

    assert result.decision == "blocked"
    assert "execution_authorization_required" in result.blocked_reasons
    assert result.executor_release_granted is False
    assert result.execution_allowed is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_executor_release_grants_inert_release_without_transport(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")

    result = LiveExecutorReleaseRuntime().release(
        authorization=_authorization(),
        executor_kind="provider",
        release_ref="executor-release://wave95/provider",
        idempotency_key="wave95-provider-release-1",
    )

    assert result.decision == "release_ready"
    assert result.release_envelope_ready is True
    assert result.executor_release_granted is True
    assert result.execution_allowed is True
    assert result.live_transport_enabled is False
    assert result.network_opened is False
    assert result.handler_executed is False
    assert result.external_delivery_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False


def test_executor_release_blocks_executor_kind_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")

    result = LiveExecutorReleaseRuntime().release(
        authorization=_authorization(),
        executor_kind="gateway",
        release_ref="executor-release://wave95/provider",
        idempotency_key="wave95-provider-release-1",
    )

    assert result.decision == "blocked"
    assert "executor_kind_mismatch" in result.blocked_reasons
    assert result.executor_release_granted is False
    assert result.execution_allowed is False


def test_cli_and_python_library_executor_release(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")
    authorization = _authorization()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-executor-release",
            "--authorization-json",
            authorization.model_dump_json(),
            "--executor-kind",
            "provider",
            "--release-ref",
            "executor-release://wave95/provider",
            "--idempotency-key",
            "wave95-provider-release-1",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "release_ready"
    assert payload["executor_release_granted"] is True
    assert payload["network_opened"] is False

    library_payload = ZeusAgent().live_executor_release(
        authorization.to_payload(),
        executor_kind="provider",
        release_ref="executor-release://wave95/provider",
        idempotency_key="wave95-provider-release-1",
    )
    assert library_payload["decision"] == "release_ready"
    assert library_payload["live_transport_enabled"] is False


def _authorization():
    return LiveExecutionAuthorizationRuntime().authorize(
        envelope_kind="provider",
        envelope=_provider_envelope().to_payload(),
        operator_proof=_operator_proof(),
        required_risks=("network", "credential_material_access", "external_provider_inference"),
    )
