from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_executor_release_runtime import LiveExecutorReleaseRuntime
from zeus_agent.live_loopback_executor_runtime import LiveLoopbackExecutorRuntime
from zeus_agent.live_provider_request_runtime import LiveProviderRequestRuntime
from tests.test_wave91_provider_request_envelope import _provider_transport_lease, _secret_material
from tests.test_wave94_execution_authorization import _provider_envelope
from tests.test_wave95_executor_release import _authorization


def test_loopback_executor_blocks_without_release(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")

    result = LiveLoopbackExecutorRuntime().execute(
        release=None,
        envelope_kind="provider",
        envelope=_provider_envelope().to_payload(),
        execution_ref="loopback://wave96/provider",
    )

    assert result.decision == "blocked"
    assert "executor_release_required" in result.blocked_reasons
    assert result.loopback_executed is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_loopback_executor_runs_provider_envelope_without_external_transport(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")

    result = LiveLoopbackExecutorRuntime().execute(
        release=_release(),
        envelope_kind="provider",
        envelope=_provider_envelope().to_payload(),
        execution_ref="loopback://wave96/provider",
    )

    assert result.decision == "executed"
    assert result.executor_release_bound is True
    assert result.envelope_bound is True
    assert result.loopback_executed is True
    assert result.handler_executed is True
    assert result.provider_invoked is False
    assert result.network_opened is False
    assert result.external_delivery_opened is False
    assert result.credential_material_accessed is False
    assert result.live_transport_enabled is False
    assert result.live_production_claimed is False
    assert result.cleanup_receipt == "loopback-no-runtime-resources"


def test_loopback_executor_blocks_release_envelope_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")

    result = LiveLoopbackExecutorRuntime().execute(
        release=_release(),
        envelope_kind="provider",
        envelope=_different_provider_envelope().to_payload(),
        execution_ref="loopback://wave96/provider",
    )

    assert result.decision == "blocked"
    assert "release_envelope_mismatch" in result.blocked_reasons
    assert result.loopback_executed is False
    assert result.handler_executed is False


def test_cli_and_python_library_loopback_executor(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")
    release = _release()
    envelope = _provider_envelope()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-loopback-execute",
            "--release-json",
            release.model_dump_json(),
            "--envelope-kind",
            "provider",
            "--envelope-json",
            envelope.model_dump_json(),
            "--execution-ref",
            "loopback://wave96/provider",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "executed"
    assert payload["loopback_executed"] is True
    assert payload["network_opened"] is False

    library_payload = ZeusAgent().live_loopback_execute(
        release.to_payload(),
        envelope_kind="provider",
        envelope=envelope.to_payload(),
        execution_ref="loopback://wave96/provider",
    )
    assert library_payload["decision"] == "executed"
    assert library_payload["live_transport_enabled"] is False


def _release():
    return LiveExecutorReleaseRuntime().release(
        authorization=_authorization(),
        executor_kind="provider",
        release_ref="executor-release://wave95/provider",
        idempotency_key="wave95-provider-release-1",
    )


def _different_provider_envelope():
    return LiveProviderRequestRuntime().prepare(
        transport_lease=_provider_transport_lease(),
        secret_material=_secret_material(),
        provider_kind="openai_compatible",
        model_id="gpt-test",
        endpoint="https://api.openai.local/v1/chat/completions",
        message="summarize different local state",
    )
