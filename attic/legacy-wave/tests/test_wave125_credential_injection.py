from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionRuntime
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightRuntime
from tests.test_wave107_provider_http_transport import _secret_material as _provider_secret_material
from tests.test_wave109_mcp_http_transport import _secret_material as _mcp_secret_material
from tests.test_wave111_remote_credential_handoff import _gateway_policy, _mcp_policy, _provider_policy
from tests.test_wave112_remote_executor_preflight import _gateway_handoff, _mcp_handoff, _provider_handoff
from tests.test_wave114_gateway_external_transport import _gateway_preflight
from tests.test_wave115_mcp_external_transport import _mcp_preflight
from tests.test_wave122_provider_direct_adapter import _provider_claim
from tests.test_wave123_gateway_delivery_adapter import _gateway_claim
from tests.test_wave124_mcp_remote_adapter import _mcp_claim
from tests.test_wave92_gateway_delivery_envelope import _secret_material as _gateway_secret_material


def test_credential_injection_binds_provider_claim_and_secret_without_secret_echo(monkeypatch, tmp_path: Path) -> None:
    material = "provider-" + "material-value"
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", material)
    policy = _provider_policy()
    handoff = _provider_handoff()
    preflight = _provider_preflight(policy, handoff)
    secret_material = _provider_secret_material("api.openai.local")

    result = LiveCredentialInjectionRuntime().prepare(
        adapter_kind="provider",
        claim=_provider_claim(tmp_path),
        policy=policy,
        preflight=preflight,
        handoff=handoff,
        secret_material=secret_material,
        injection_ref="credential-injection://wave125/provider",
    )

    payload = result.to_payload()
    assert result.decision == "injection_ready"
    assert result.credential_injection_ready is True
    assert result.production_claim_bound is True
    assert result.policy_bound is True
    assert result.preflight_bound is True
    assert result.credential_handoff_bound is True
    assert result.secret_material_bound is True
    assert result.material_access_proof_bound is True
    assert result.sealed_header_ref_ready is True
    assert result.header_value_ref == handoff.header_value_ref
    assert result.material_proof_id == secret_material.material_proof_id
    assert result.credential_material_accessed is False
    assert result.material_released is False
    assert result.raw_secret_returned is False
    assert result.network_opened is False
    assert result.live_production_claimed is False
    assert material not in json.dumps(payload)


def test_credential_injection_accepts_gateway_and_mcp(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")

    gateway = LiveCredentialInjectionRuntime().prepare(
        adapter_kind="gateway",
        claim=_gateway_claim(tmp_path),
        policy=_gateway_policy(),
        preflight=_gateway_preflight(),
        handoff=_gateway_handoff(),
        secret_material=_gateway_secret_material(),
        injection_ref="credential-injection://wave125/gateway",
    )
    mcp = LiveCredentialInjectionRuntime().prepare(
        adapter_kind="mcp",
        claim=_mcp_claim(tmp_path),
        policy=_mcp_policy(),
        preflight=_mcp_preflight(),
        handoff=_mcp_handoff(),
        secret_material=_mcp_secret_material("mcp.github.local"),
        injection_ref="credential-injection://wave125/mcp",
    )

    for result in (gateway, mcp):
        assert result.decision == "injection_ready"
        assert result.credential_injection_ready is True
        assert result.network_opened is False
        assert result.external_delivery_opened is False
        assert result.raw_secret_returned is False
        assert result.live_production_claimed is False
    assert mcp.header_name == "X-API-Key"


def test_credential_injection_blocks_mismatched_claim_adapter(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")

    result = LiveCredentialInjectionRuntime().prepare(
        adapter_kind="provider",
        claim=_mcp_claim(tmp_path),
        policy=_provider_policy(),
        preflight=_provider_preflight(_provider_policy(), _provider_handoff()),
        handoff=_provider_handoff(),
        secret_material=_provider_secret_material("api.openai.local"),
        injection_ref="credential-injection://wave125/wrong-claim",
    )

    assert result.decision == "blocked"
    assert "production_claim_adapter_mismatch" in result.blocked_reasons
    assert result.credential_injection_ready is False
    assert result.network_opened is False


def test_credential_injection_blocks_handoff_material_mismatch(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    handoff = _provider_handoff().model_copy(update={"header_value_ref": "secret-proof://wrong-material"})

    result = LiveCredentialInjectionRuntime().prepare(
        adapter_kind="provider",
        claim=_provider_claim(tmp_path),
        policy=_provider_policy(),
        preflight=_provider_preflight(_provider_policy(), _provider_handoff()),
        handoff=handoff,
        secret_material=_provider_secret_material("api.openai.local"),
        injection_ref="credential-injection://wave125/wrong-handoff",
    )

    assert result.decision == "blocked"
    assert "credential_handoff_material_mismatch" in result.blocked_reasons
    assert result.material_released is False
    assert result.raw_secret_returned is False


def test_credential_injection_blocks_secret_leak(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    leaking_material = _provider_secret_material("api.openai.local").model_copy(update={"raw_secret_returned": True})

    result = LiveCredentialInjectionRuntime().prepare(
        adapter_kind="provider",
        claim=_provider_claim(tmp_path),
        policy=_provider_policy(),
        preflight=_provider_preflight(_provider_policy(), _provider_handoff()),
        handoff=_provider_handoff(),
        secret_material=leaking_material,
        injection_ref="credential-injection://wave125/leak",
    )

    assert result.decision == "blocked"
    assert "secret_material_leak_detected" in result.blocked_reasons
    assert result.raw_secret_returned is False


def test_cli_and_python_library_credential_injection(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    claim = _provider_claim(tmp_path)
    policy = _provider_policy()
    handoff = _provider_handoff()
    preflight = _provider_preflight(policy, handoff)
    secret_material = _provider_secret_material("api.openai.local")

    completed = CliRunner().invoke(
        app,
        [
            "live-credential-injection",
            "--adapter-kind",
            "provider",
            "--claim-json",
            claim.model_dump_json(),
            "--policy-json",
            policy.model_dump_json(),
            "--preflight-json",
            preflight.model_dump_json(),
            "--handoff-json",
            handoff.model_dump_json(),
            "--secret-material-json",
            secret_material.model_dump_json(),
            "--injection-ref",
            "credential-injection://wave125/provider",
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).live_credential_injection(
        claim.to_payload(),
        policy.to_payload(),
        preflight.to_payload(),
        handoff.to_payload(),
        secret_material.to_payload(),
        adapter_kind="provider",
        injection_ref="credential-injection://wave125/provider-library",
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "injection_ready"
    assert payload["credential_injection_ready"] is True
    assert payload["sealed_header_ref_ready"] is True
    assert payload["raw_secret_returned"] is False
    assert library_payload["decision"] == "injection_ready"


def _provider_preflight(policy, handoff):
    return LiveRemoteExecutorPreflightRuntime().plan(
        policy=policy,
        handoff=handoff,
        executor_kind="provider",
        executor_ref="remote-executor://wave125/provider",
        idempotency_key="wave125-provider-injection",
        teardown_ref=policy.teardown_ref or "",
        timeout_ms=1500,
        retry_attempts=1,
    )
