from __future__ import annotations

from pathlib import Path

from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionRuntime
from zeus_agent.live_gateway_delivery_adapter_runtime import (
    LiveGatewayDeliveryAdapterReceipt,
    LiveGatewayDeliveryAdapterRequest,
    LiveGatewayDeliveryAdapterRuntime,
)
from zeus_agent.live_mcp_remote_adapter_runtime import (
    LiveMcpRemoteAdapterReceipt,
    LiveMcpRemoteAdapterRequest,
    LiveMcpRemoteAdapterRuntime,
)
from zeus_agent.live_provider_direct_adapter_runtime import (
    LiveProviderDirectAdapterReceipt,
    LiveProviderDirectAdapterRequest,
    LiveProviderDirectAdapterRuntime,
)
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightRuntime
from tests.test_wave103_gateway_loopback_transport import _gateway_envelope
from tests.test_wave107_provider_http_transport import _secret_material as _provider_secret_material
from tests.test_wave109_mcp_http_transport import _secret_material as _mcp_secret_material
from tests.test_wave111_remote_credential_handoff import _gateway_policy, _mcp_policy, _provider_policy
from tests.test_wave112_remote_executor_preflight import _gateway_handoff, _mcp_handoff, _provider_handoff
from tests.test_wave113_provider_external_transport import _provider_request
from tests.test_wave114_gateway_external_transport import _gateway_preflight
from tests.test_wave115_mcp_external_transport import _mcp_preflight, _mcp_request
from tests.test_wave122_provider_direct_adapter import _provider_claim
from tests.test_wave123_gateway_delivery_adapter import _gateway_claim
from tests.test_wave124_mcp_remote_adapter import _mcp_claim
from tests.test_wave92_gateway_delivery_envelope import _secret_material as _gateway_secret_material


class _ProviderClient:
    def __init__(self) -> None:
        self.requests: list[LiveProviderDirectAdapterRequest] = []

    def send(self, request: LiveProviderDirectAdapterRequest) -> LiveProviderDirectAdapterReceipt:
        self.requests.append(request)
        return LiveProviderDirectAdapterReceipt(
            status_code=200,
            latency_ms=10,
            response_payload={"ok": True},
            cleanup_receipt="provider-direct-client-closed",
        )


class _GatewayClient:
    def __init__(self) -> None:
        self.requests: list[LiveGatewayDeliveryAdapterRequest] = []

    def deliver(self, request: LiveGatewayDeliveryAdapterRequest) -> LiveGatewayDeliveryAdapterReceipt:
        self.requests.append(request)
        return LiveGatewayDeliveryAdapterReceipt(
            status_code=200,
            latency_ms=11,
            response_payload={"ok": True},
            external_delivery_opened=True,
            cleanup_receipt="gateway-delivery-adapter-client-closed",
        )


class _McpClient:
    def __init__(self) -> None:
        self.requests: list[LiveMcpRemoteAdapterRequest] = []

    def invoke(self, request: LiveMcpRemoteAdapterRequest) -> LiveMcpRemoteAdapterReceipt:
        self.requests.append(request)
        return LiveMcpRemoteAdapterReceipt(
            status_code=200,
            latency_ms=12,
            response_payload={"ok": True},
            cleanup_receipt="mcp-remote-adapter-client-closed",
        )


def test_provider_direct_adapter_requires_credential_injection(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    bundle = _provider_bundle(tmp_path)

    result = LiveProviderDirectAdapterRuntime().execute(
        claim=bundle["claim"],
        policy=bundle["policy"],
        preflight=bundle["preflight"],
        handoff=bundle["handoff"],
        credential_injection=None,
        provider_envelope=_provider_request(),
        client=_ProviderClient(),
        execution_ref="provider-direct://wave126/missing-injection",
    )

    assert result.decision == "blocked"
    assert "credential_injection_required" in result.blocked_reasons
    assert result.provider_invoked is False
    assert result.network_opened is False


def test_provider_direct_adapter_uses_injection_header_ref(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    bundle = _provider_bundle(tmp_path)
    client = _ProviderClient()

    result = LiveProviderDirectAdapterRuntime().execute(
        claim=bundle["claim"],
        policy=bundle["policy"],
        preflight=bundle["preflight"],
        handoff=bundle["handoff"],
        credential_injection=bundle["injection"],
        provider_envelope=_provider_request(),
        client=client,
        execution_ref="provider-direct://wave126/provider",
    )

    assert result.decision == "executed"
    assert result.credential_injection_bound is True
    assert result.provider_invoked is True
    assert client.requests[0].header_value_ref == bundle["injection"].header_value_ref


def test_gateway_and_mcp_adapters_require_matching_injection(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    gateway = _gateway_bundle(tmp_path)
    mcp = _mcp_bundle(tmp_path)

    gateway_result = LiveGatewayDeliveryAdapterRuntime().execute(
        claim=gateway["claim"],
        policy=gateway["policy"],
        preflight=gateway["preflight"],
        handoff=gateway["handoff"],
        credential_injection=gateway["injection"],
        gateway_envelope=_gateway_envelope(),
        client=_GatewayClient(),
        execution_ref="gateway-delivery://wave126/gateway",
    )
    mcp_result = LiveMcpRemoteAdapterRuntime().execute(
        claim=mcp["claim"],
        policy=mcp["policy"],
        preflight=mcp["preflight"],
        handoff=mcp["handoff"],
        credential_injection=mcp["injection"],
        mcp_envelope=_mcp_request(),
        client=_McpClient(),
        execution_ref="mcp-remote://wave126/mcp",
    )

    assert gateway_result.decision == "executed"
    assert gateway_result.credential_injection_bound is True
    assert mcp_result.decision == "executed"
    assert mcp_result.credential_injection_bound is True


def test_adapter_blocks_injection_bound_to_other_claim(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    first = _provider_bundle(tmp_path)
    second = _provider_bundle(tmp_path)
    mismatched = second["injection"].model_copy(update={"claim_id": "live-production-claim-other"})

    result = LiveProviderDirectAdapterRuntime().execute(
        claim=first["claim"],
        policy=first["policy"],
        preflight=first["preflight"],
        handoff=first["handoff"],
        credential_injection=mismatched,
        provider_envelope=_provider_request(),
        client=_ProviderClient(),
        execution_ref="provider-direct://wave126/wrong-injection",
    )

    assert result.decision == "blocked"
    assert "credential_injection_claim_mismatch" in result.blocked_reasons
    assert result.network_opened is False


def _provider_bundle(tmp_path: Path):
    claim = _provider_claim(tmp_path)
    policy = _provider_policy()
    handoff = _provider_handoff()
    preflight = LiveRemoteExecutorPreflightRuntime().plan(
        policy=policy,
        handoff=handoff,
        executor_kind="provider",
        executor_ref="remote-executor://wave126/provider",
        idempotency_key="wave126-provider",
        teardown_ref=policy.teardown_ref or "",
        timeout_ms=1500,
        retry_attempts=1,
    )
    injection = LiveCredentialInjectionRuntime().prepare(
        adapter_kind="provider",
        claim=claim,
        policy=policy,
        preflight=preflight,
        handoff=handoff,
        secret_material=_provider_secret_material("api.openai.local"),
        injection_ref="credential-injection://wave126/provider",
    )
    return {"claim": claim, "policy": policy, "preflight": preflight, "handoff": handoff, "injection": injection}


def _gateway_bundle(tmp_path: Path):
    claim = _gateway_claim(tmp_path)
    policy = _gateway_policy()
    handoff = _gateway_handoff()
    return {
        "claim": claim,
        "policy": policy,
        "preflight": _gateway_preflight(),
        "handoff": handoff,
        "injection": LiveCredentialInjectionRuntime().prepare(
            adapter_kind="gateway",
            claim=claim,
            policy=policy,
            preflight=_gateway_preflight(),
            handoff=handoff,
            secret_material=_gateway_secret_material(),
            injection_ref="credential-injection://wave126/gateway",
        ),
    }


def _mcp_bundle(tmp_path: Path):
    claim = _mcp_claim(tmp_path)
    policy = _mcp_policy()
    handoff = _mcp_handoff()
    return {
        "claim": claim,
        "policy": policy,
        "preflight": _mcp_preflight(),
        "handoff": handoff,
        "injection": LiveCredentialInjectionRuntime().prepare(
            adapter_kind="mcp",
            claim=claim,
            policy=policy,
            preflight=_mcp_preflight(),
            handoff=handoff,
            secret_material=_mcp_secret_material("mcp.github.local"),
            injection_ref="credential-injection://wave126/mcp",
        ),
    }
