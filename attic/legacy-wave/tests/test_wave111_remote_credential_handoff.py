from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_remote_credential_handoff_runtime import LiveRemoteCredentialHandoffRuntime
from tests.test_wave103_gateway_loopback_transport import _gateway_activation, _gateway_adapter_plan
from tests.test_wave107_provider_http_transport import (
    _activation as _provider_activation,
    _adapter_plan as _provider_adapter_plan,
    _provider_envelope,
    _secret_material as _provider_secret_material,
)
from tests.test_wave109_mcp_http_transport import (
    _activation as _mcp_activation,
    _adapter_plan as _mcp_adapter_plan,
    _mcp_envelope,
    _secret_material as _mcp_secret_material,
)
from tests.test_wave110_remote_transport_policy import _policy_kwargs
from tests.test_wave92_gateway_delivery_envelope import _secret_material as _gateway_secret_material


def test_remote_credential_handoff_ready_without_raw_secret(monkeypatch) -> None:
    material = "provider-" + "material-value"
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", material)

    result = LiveRemoteCredentialHandoffRuntime().prepare(
        policy=_provider_policy(),
        secret_material=_provider_secret_material("api.openai.local"),
        handoff_ref="credential-handoff://wave111/provider",
        auth_scheme="bearer",
        header_name="Authorization",
    )

    payload = result.to_payload()
    assert result.decision == "handoff_ready"
    assert result.credential_handoff_ready is True
    assert result.policy_bound is True
    assert result.secret_material_bound is True
    assert result.header_value_ref.startswith("secret-proof://")
    assert result.credential_material_accessed is False
    assert result.material_released is False
    assert result.raw_secret_returned is False
    assert result.network_opened is False
    assert result.live_production_claimed is False
    assert material not in json.dumps(payload)


def test_remote_credential_handoff_blocks_unready_policy_and_secret_leak(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    leaked_material = _provider_secret_material("api.openai.local").model_copy(update={"raw_secret_returned": True})

    unready_policy = ZeusAgent().live_remote_transport_policy(
        _provider_activation(_provider_envelope("https://api.openai.local/v1/chat/completions", "api.openai.local")).to_payload(),
        adapter_kind="provider",
        adapter_plan=_provider_adapter_plan(
            _provider_envelope("https://api.openai.local/v1/chat/completions", "api.openai.local")
        ).to_payload(),
        transport_kind="external_http",
        remote_target="https://api.openai.local/v1/chat/completions",
        allowed_remote_targets=(),
        **_policy_kwargs("external.openai.readonly", "api.openai.local"),
    )
    blocked_policy = LiveRemoteCredentialHandoffRuntime().prepare(
        policy=_provider_policy().model_validate(unready_policy),
        secret_material=_provider_secret_material("api.openai.local"),
        handoff_ref="credential-handoff://wave111/provider",
        auth_scheme="bearer",
        header_name="Authorization",
    )
    blocked_secret = LiveRemoteCredentialHandoffRuntime().prepare(
        policy=_provider_policy(),
        secret_material=leaked_material,
        handoff_ref="credential-handoff://wave111/provider",
        auth_scheme="bearer",
        header_name="Authorization",
    )

    assert blocked_policy.decision == "blocked"
    assert "remote_policy_not_ready" in blocked_policy.blocked_reasons
    assert blocked_policy.network_opened is False
    assert blocked_secret.decision == "blocked"
    assert "secret_material_leak_detected" in blocked_secret.blocked_reasons
    assert blocked_secret.raw_secret_returned is False


def test_remote_credential_handoff_accepts_gateway_and_mcp(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")

    gateway = LiveRemoteCredentialHandoffRuntime().prepare(
        policy=_gateway_policy(),
        secret_material=_gateway_secret_material(),
        handoff_ref="credential-handoff://wave111/gateway",
        auth_scheme="bearer",
        header_name="Authorization",
    )
    mcp = LiveRemoteCredentialHandoffRuntime().prepare(
        policy=_mcp_policy(),
        secret_material=_mcp_secret_material("mcp.github.local"),
        handoff_ref="credential-handoff://wave111/mcp",
        auth_scheme="api_key",
        header_name="X-API-Key",
    )

    for result in (gateway, mcp):
        assert result.decision == "handoff_ready"
        assert result.credential_handoff_ready is True
        assert result.network_opened is False
        assert result.external_delivery_opened is False
        assert result.raw_secret_returned is False
        assert result.live_production_claimed is False
    assert mcp.header_name == "X-API-Key"


def test_cli_and_python_library_remote_credential_handoff(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    policy = _provider_policy()
    secret_material = _provider_secret_material("api.openai.local")
    completed = CliRunner().invoke(
        app,
        [
            "live-remote-credential-handoff",
            "--policy-json",
            policy.model_dump_json(),
            "--secret-material-json",
            secret_material.model_dump_json(),
            "--handoff-ref",
            "credential-handoff://wave111/provider",
            "--auth-scheme",
            "bearer",
            "--header-name",
            "Authorization",
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_remote_credential_handoff(
        policy.to_payload(),
        secret_material.to_payload(),
        handoff_ref="credential-handoff://wave111/provider-library",
        auth_scheme="bearer",
        header_name="Authorization",
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "handoff_ready"
    assert payload["raw_secret_returned"] is False
    assert payload["network_opened"] is False
    assert library_payload["decision"] == "handoff_ready"
    assert library_payload["material_released"] is False


def _provider_policy():
    envelope = _provider_envelope("https://api.openai.local/v1/chat/completions", "api.openai.local")
    return _agent_policy(
        activation=_provider_activation(envelope),
        adapter_kind="provider",
        adapter_plan=_provider_adapter_plan(envelope),
        transport_kind="external_http",
        remote_target="https://api.openai.local/v1/chat/completions",
        allowed_remote_targets=("api.openai.local",),
        scope="external.openai.readonly",
        target_identity="api.openai.local",
    )


def _gateway_policy():
    return _agent_policy(
        activation=_gateway_activation(),
        adapter_kind="gateway",
        adapter_plan=_gateway_adapter_plan(),
        transport_kind="external_http",
        remote_target="slack://ops",
        allowed_remote_targets=("slack://ops",),
        scope="external.slack.write",
        target_identity="slack://ops",
    )


def _mcp_policy():
    envelope = _mcp_envelope("https://mcp.github.local/rpc", "mcp.github.local")
    return _agent_policy(
        activation=_mcp_activation(envelope),
        adapter_kind="mcp",
        adapter_plan=_mcp_adapter_plan(envelope),
        transport_kind="remote_server",
        remote_target="https://mcp.github.local/rpc",
        allowed_remote_targets=("mcp.github.local",),
        scope="external.github.readonly",
        target_identity="mcp.github.local",
    )


def _agent_policy(
    *,
    activation,
    adapter_kind: str,
    adapter_plan,
    transport_kind: str,
    remote_target: str,
    allowed_remote_targets: tuple[str, ...],
    scope: str,
    target_identity: str,
):
    payload = ZeusAgent().live_remote_transport_policy(
        activation.to_payload(),
        adapter_kind=adapter_kind,
        adapter_plan=adapter_plan.to_payload(),
        transport_kind=transport_kind,
        remote_target=remote_target,
        allowed_remote_targets=allowed_remote_targets,
        **_policy_kwargs(scope, target_identity),
    )
    from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult

    return LiveRemoteTransportPolicyResult.model_validate(payload)
