from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_provider_adapter_runtime import LiveProviderAdapterRuntime
from tests.test_wave94_execution_authorization import _provider_envelope
from tests.test_wave96_loopback_executor import _release


def test_provider_adapter_plan_blocks_without_release(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")

    result = LiveProviderAdapterRuntime().plan(
        release=None,
        provider_envelope=_provider_envelope(),
        transport_mode="dry_run",
        timeout_ms=1500,
        retry_attempts=1,
        idempotency_key="wave97-provider-adapter-1",
    )

    assert result.decision == "blocked"
    assert "executor_release_required" in result.blocked_reasons
    assert result.adapter_plan_ready is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_provider_adapter_plan_prepares_dry_run_without_network(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")

    result = LiveProviderAdapterRuntime().plan(
        release=_release(),
        provider_envelope=_provider_envelope(),
        transport_mode="dry_run",
        timeout_ms=1500,
        retry_attempts=1,
        idempotency_key="wave97-provider-adapter-1",
    )

    assert result.decision == "planned"
    assert result.adapter_plan_ready is True
    assert result.release_bound is True
    assert result.provider_envelope_bound is True
    assert result.live_transport_requested is False
    assert result.provider_invoked is False
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.raw_secret_returned is False
    assert result.live_transport_enabled is False
    assert result.live_production_claimed is False


def test_provider_adapter_plan_blocks_live_transport_until_executor_exists(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")

    result = LiveProviderAdapterRuntime().plan(
        release=_release(),
        provider_envelope=_provider_envelope(),
        transport_mode="live",
        timeout_ms=1500,
        retry_attempts=1,
        idempotency_key="wave97-provider-adapter-1",
    )

    assert result.decision == "blocked"
    assert "provider_live_transport_not_implemented" in result.blocked_reasons
    assert result.live_transport_requested is True
    assert result.network_opened is False
    assert result.provider_invoked is False


def test_cli_and_python_library_provider_adapter_plan(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")
    release = _release()
    envelope = _provider_envelope()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-provider-adapter-plan",
            "--release-json",
            release.model_dump_json(),
            "--provider-envelope-json",
            envelope.model_dump_json(),
            "--transport-mode",
            "dry_run",
            "--timeout-ms",
            "1500",
            "--retry-attempts",
            "1",
            "--idempotency-key",
            "wave97-provider-adapter-1",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "planned"
    assert payload["network_opened"] is False

    library_payload = ZeusAgent().live_provider_adapter_plan(
        release.to_payload(),
        provider_envelope=envelope.to_payload(),
        transport_mode="dry_run",
        timeout_ms=1500,
        retry_attempts=1,
        idempotency_key="wave97-provider-adapter-1",
    )
    assert library_payload["decision"] == "planned"
    assert library_payload["provider_invoked"] is False
