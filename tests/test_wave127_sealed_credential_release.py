from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionRuntime
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightRuntime
from zeus_agent.live_sealed_credential_runtime import (
    LiveSealedCredential,
    LiveSealedCredentialReceipt,
    LiveSealedCredentialRuntime,
)
from tests.test_wave107_provider_http_transport import _secret_material as _provider_secret_material
from tests.test_wave109_mcp_http_transport import _secret_material as _mcp_secret_material
from tests.test_wave111_remote_credential_handoff import _mcp_policy, _provider_policy
from tests.test_wave112_remote_executor_preflight import _mcp_handoff, _provider_handoff
from tests.test_wave122_provider_direct_adapter import _provider_claim
from tests.test_wave124_mcp_remote_adapter import _mcp_claim


class _RecordingConsumer:
    def __init__(self, consumer_ref: str) -> None:
        self.consumer_ref = consumer_ref
        self.values: list[str] = []

    def consume(self, credential: LiveSealedCredential) -> LiveSealedCredentialReceipt:
        self.values.append(credential.reveal_for_transport())
        return LiveSealedCredentialReceipt(
            consumer_ref=self.consumer_ref,
            credential_value_received=True,
            header_name_seen=credential.header_name,
            header_value_ref_seen=credential.header_value_ref,
        )


def test_sealed_credential_release_passes_raw_value_only_to_consumer(monkeypatch, tmp_path: Path) -> None:
    material = "provider-" + "material-value"
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", material)
    injection, secret_material = _provider_injection(tmp_path)
    consumer = _RecordingConsumer("consumer://wave127/provider")

    result = LiveSealedCredentialRuntime().release(
        injection=injection,
        secret_material=secret_material,
        consumer=consumer,
        release_ref="sealed-credential://wave127/provider",
    )

    payload = result.to_payload()
    assert result.decision == "released"
    assert result.sealed_credential_released is True
    assert result.credential_material_accessed is True
    assert result.material_released_to_consumer is True
    assert result.material_released is False
    assert result.raw_secret_returned is False
    assert result.network_opened is False
    assert result.live_production_claimed is False
    assert consumer.values == ["Bearer " + material]
    assert material not in json.dumps(payload)


def test_sealed_credential_release_supports_api_key_headers(monkeypatch, tmp_path: Path) -> None:
    material = "mcp-" + "material-value"
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", material)
    injection, secret_material = _mcp_injection(tmp_path)
    consumer = _RecordingConsumer("consumer://wave127/mcp")

    result = LiveSealedCredentialRuntime().release(
        injection=injection,
        secret_material=secret_material,
        consumer=consumer,
        release_ref="sealed-credential://wave127/mcp",
    )

    assert result.decision == "released"
    assert consumer.values == [material]
    assert result.header_name == "X-API-Key"
    assert material not in json.dumps(result.to_payload())


def test_sealed_credential_release_blocks_material_mismatch(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    injection, _secret_material = _provider_injection(tmp_path)
    mismatched_material = _mcp_secret_material("mcp.github.local")

    result = LiveSealedCredentialRuntime().release(
        injection=injection,
        secret_material=mismatched_material,
        consumer=_RecordingConsumer("consumer://wave127/mismatch"),
        release_ref="sealed-credential://wave127/mismatch",
    )

    assert result.decision == "blocked"
    assert "credential_injection_material_mismatch" in result.blocked_reasons
    assert result.credential_material_accessed is False
    assert result.raw_secret_returned is False


def test_cli_and_python_library_sealed_credential_release(monkeypatch, tmp_path: Path) -> None:
    material = "provider-" + "material-value"
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", material)
    injection, secret_material = _provider_injection(tmp_path)

    completed = CliRunner().invoke(
        app,
        [
            "live-sealed-credential-release",
            "--injection-json",
            injection.model_dump_json(),
            "--secret-material-json",
            secret_material.model_dump_json(),
            "--consumer-ref",
            "consumer://wave127/provider-cli",
            "--release-ref",
            "sealed-credential://wave127/provider-cli",
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).live_sealed_credential_release(
        injection.to_payload(),
        secret_material.to_payload(),
        consumer_ref="consumer://wave127/provider-library",
        release_ref="sealed-credential://wave127/provider-library",
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "released"
    assert payload["sealed_credential_released"] is True
    assert payload["raw_secret_returned"] is False
    assert material not in completed.stdout
    assert library_payload["decision"] == "released"
    assert material not in json.dumps(library_payload)


def _provider_injection(tmp_path: Path):
    claim = _provider_claim(tmp_path)
    policy = _provider_policy()
    handoff = _provider_handoff()
    preflight = LiveRemoteExecutorPreflightRuntime().plan(
        policy=policy,
        handoff=handoff,
        executor_kind="provider",
        executor_ref="remote-executor://wave127/provider",
        idempotency_key="wave127-provider",
        teardown_ref=policy.teardown_ref or "",
        timeout_ms=1500,
        retry_attempts=1,
    )
    secret_material = _provider_secret_material("api.openai.local")
    return (
        LiveCredentialInjectionRuntime().prepare(
            adapter_kind="provider",
            claim=claim,
            policy=policy,
            preflight=preflight,
            handoff=handoff,
            secret_material=secret_material,
            injection_ref="credential-injection://wave127/provider",
        ),
        secret_material,
    )


def _mcp_injection(tmp_path: Path):
    claim = _mcp_claim(tmp_path)
    policy = _mcp_policy()
    handoff = _mcp_handoff()
    preflight = LiveRemoteExecutorPreflightRuntime().plan(
        policy=policy,
        handoff=handoff,
        executor_kind="mcp",
        executor_ref="remote-executor://wave127/mcp",
        idempotency_key="wave127-mcp",
        teardown_ref=policy.teardown_ref or "",
        timeout_ms=1500,
        retry_attempts=1,
    )
    secret_material = _mcp_secret_material("mcp.github.local")
    return (
        LiveCredentialInjectionRuntime().prepare(
            adapter_kind="mcp",
            claim=claim,
            policy=policy,
            preflight=preflight,
            handoff=handoff,
            secret_material=secret_material,
            injection_ref="credential-injection://wave127/mcp",
        ),
        secret_material,
    )
