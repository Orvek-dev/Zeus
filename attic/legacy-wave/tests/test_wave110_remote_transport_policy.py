from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyRuntime
from tests.test_wave103_gateway_loopback_transport import _gateway_activation, _gateway_adapter_plan
from tests.test_wave107_provider_http_transport import (
    _activation as _provider_activation,
    _adapter_plan as _provider_adapter_plan,
    _provider_envelope,
)
from tests.test_wave109_mcp_http_transport import (
    _activation as _mcp_activation,
    _adapter_plan as _mcp_adapter_plan,
    _mcp_envelope,
)


def test_provider_remote_policy_ready_without_opening_network(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    envelope = _provider_envelope("https://api.openai.local/v1/chat/completions", "api.openai.local")

    result = LiveRemoteTransportPolicyRuntime().plan(
        activation=_provider_activation(envelope),
        adapter_kind="provider",
        adapter_plan=_provider_adapter_plan(envelope),
        transport_kind="external_http",
        remote_target="https://api.openai.local/v1/chat/completions",
        allowed_remote_targets=("api.openai.local",),
        **_policy_kwargs("external.openai.readonly", "api.openai.local"),
    )

    assert result.decision == "policy_ready"
    assert result.remote_transport_policy_ready is True
    assert result.activation_bound is True
    assert result.adapter_plan_bound is True
    assert result.remote_target_allowlisted is True
    assert result.credential_scope_bound is True
    assert result.credential_binding_bound is True
    assert result.live_transport_authorized is True
    assert result.live_transport_enabled is False
    assert result.execution_allowed is False
    assert result.network_opened is False
    assert result.non_loopback_network_opened is False
    assert result.live_production_claimed is False


def test_provider_remote_policy_blocks_missing_allowlist_and_loopback(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    remote_envelope = _provider_envelope("https://api.openai.local/v1/chat/completions", "api.openai.local")
    loopback_envelope = _provider_envelope("http://127.0.0.1/v1/chat/completions", "127.0.0.1")

    missing_allowlist = LiveRemoteTransportPolicyRuntime().plan(
        activation=_provider_activation(remote_envelope),
        adapter_kind="provider",
        adapter_plan=_provider_adapter_plan(remote_envelope),
        transport_kind="external_http",
        remote_target="https://api.openai.local/v1/chat/completions",
        allowed_remote_targets=(),
        **_policy_kwargs("external.openai.readonly", "api.openai.local"),
    )
    loopback = LiveRemoteTransportPolicyRuntime().plan(
        activation=_provider_activation(loopback_envelope),
        adapter_kind="provider",
        adapter_plan=_provider_adapter_plan(loopback_envelope),
        transport_kind="external_http",
        remote_target="http://127.0.0.1/v1/chat/completions",
        allowed_remote_targets=("127.0.0.1",),
        **_policy_kwargs("external.openai.readonly", "127.0.0.1"),
    )

    assert missing_allowlist.decision == "blocked"
    assert "remote_target_allowlist_required" in missing_allowlist.blocked_reasons
    assert "remote_target_not_allowlisted" in missing_allowlist.blocked_reasons
    assert missing_allowlist.network_opened is False
    assert loopback.decision == "blocked"
    assert "remote_target_must_not_be_loopback" in loopback.blocked_reasons
    assert loopback.network_opened is False


def test_gateway_and_mcp_remote_policy_ready(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    mcp_envelope = _mcp_envelope("https://mcp.github.local/rpc", "mcp.github.local")

    gateway = LiveRemoteTransportPolicyRuntime().plan(
        activation=_gateway_activation(),
        adapter_kind="gateway",
        adapter_plan=_gateway_adapter_plan(),
        transport_kind="external_http",
        remote_target="slack://ops",
        allowed_remote_targets=("slack://ops",),
        **_policy_kwargs("external.slack.write", "slack://ops"),
    )
    mcp = LiveRemoteTransportPolicyRuntime().plan(
        activation=_mcp_activation(mcp_envelope),
        adapter_kind="mcp",
        adapter_plan=_mcp_adapter_plan(mcp_envelope),
        transport_kind="remote_server",
        remote_target="https://mcp.github.local/rpc",
        allowed_remote_targets=("mcp.github.local",),
        **_policy_kwargs("external.github.readonly", "mcp.github.local"),
    )

    for result in (gateway, mcp):
        assert result.decision == "policy_ready"
        assert result.remote_transport_policy_ready is True
        assert result.network_opened is False
        assert result.external_delivery_opened is False
        assert result.credential_material_accessed is False
        assert result.live_production_claimed is False
    assert mcp.server_started is False
    assert mcp.resources_enabled is False
    assert mcp.prompts_enabled is False


def test_mcp_remote_policy_blocks_resources_and_prompts(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    envelope = _mcp_envelope("https://mcp.github.local/rpc", "mcp.github.local")

    result = LiveRemoteTransportPolicyRuntime().plan(
        activation=_mcp_activation(envelope),
        adapter_kind="mcp",
        adapter_plan=_mcp_adapter_plan(envelope),
        transport_kind="remote_server",
        remote_target="https://mcp.github.local/rpc",
        allowed_remote_targets=("mcp.github.local",),
        resources_requested=True,
        prompts_requested=True,
        **_policy_kwargs("external.github.readonly", "mcp.github.local"),
    )

    assert result.decision == "blocked"
    assert "mcp_resources_require_separate_policy" in result.blocked_reasons
    assert "mcp_prompts_require_separate_policy" in result.blocked_reasons
    assert result.server_started is False
    assert result.network_opened is False


def test_cli_and_python_library_remote_policy(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    envelope = _provider_envelope("https://api.openai.local/v1/chat/completions", "api.openai.local")
    activation = _provider_activation(envelope)
    adapter_plan = _provider_adapter_plan(envelope)
    completed = CliRunner().invoke(
        app,
        [
            "live-remote-transport-policy",
            "--activation-json",
            activation.model_dump_json(),
            "--adapter-kind",
            "provider",
            "--adapter-plan-json",
            adapter_plan.model_dump_json(),
            "--transport-kind",
            "external_http",
            "--remote-target",
            "https://api.openai.local/v1/chat/completions",
            "--allow-remote",
            "api.openai.local",
            "--credential-scope",
            "external.openai.readonly",
            "--credential-binding-ref",
            "credential-binding://external.openai.readonly@api.openai.local",
            "--policy-ref",
            "remote-policy://wave110/provider",
            "--audit-ref",
            "live-audit://wave110/provider",
            "--redaction-ref",
            "live-response://wave110/provider",
            "--teardown-ref",
            "teardown://wave110/provider",
            "--production-review-ref",
            "review://wave110/provider",
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_remote_transport_policy(
        activation.to_payload(),
        adapter_kind="provider",
        adapter_plan=adapter_plan.to_payload(),
        transport_kind="external_http",
        remote_target="https://api.openai.local/v1/chat/completions",
        allowed_remote_targets=("api.openai.local",),
        **_policy_kwargs("external.openai.readonly", "api.openai.local"),
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "policy_ready"
    assert payload["network_opened"] is False
    assert payload["live_production_claimed"] is False
    assert library_payload["decision"] == "policy_ready"
    assert library_payload["network_opened"] is False


def _policy_kwargs(scope: str, target_identity: str):
    return {
        "credential_scope": scope,
        "credential_binding_ref": "credential-binding://{0}@{1}".format(scope, target_identity),
        "policy_ref": "remote-policy://wave110/{0}".format(target_identity),
        "audit_ref": "live-audit://wave110/{0}".format(target_identity),
        "redaction_ref": "live-response://wave110/{0}".format(target_identity),
        "teardown_ref": "teardown://wave110/{0}".format(target_identity),
        "production_review_ref": "review://wave110/{0}".format(target_identity),
    }
