from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_execution_bundle_runtime import LiveExecutionBundleRuntime
from zeus_agent.live_gateway_credentialed_http_runtime import LiveGatewayCredentialedHttpResult
from zeus_agent.live_mcp_credentialed_http_runtime import LiveMcpCredentialedHttpResult
from zeus_agent.live_provider_credentialed_http_runtime import LiveProviderCredentialedHttpResult


def test_live_execution_bundle_summarizes_three_local_credentialed_proofs() -> None:
    result = LiveExecutionBundleRuntime().summarize(
        provider_result=_provider_result(),
        gateway_result=_gateway_result(),
        mcp_result=_mcp_result(),
        bundle_ref="live-execution-bundle://wave134/all",
    )

    assert result.decision == "summarized"
    assert result.bundle_ref == "live-execution-bundle://wave134/all"
    assert result.surface_count == 3
    assert result.executed_count == 3
    assert result.blocked_count == 0
    assert result.local_loopback_count == 3
    assert result.credentialed_surface_count == 3
    assert result.network_opened is True
    assert result.non_loopback_network_opened is False
    assert result.external_delivery_opened is False
    assert result.raw_secret_returned is False
    assert result.live_production_claimed is False
    assert result.no_secret_echo is True
    assert result.surfaces[0].surface_kind == "provider"
    assert result.surfaces[1].surface_kind == "gateway"
    assert result.surfaces[2].surface_kind == "mcp"
    assert "zeus live-readiness --json" in result.recommended_next_commands


def test_live_execution_bundle_blocks_without_results() -> None:
    result = LiveExecutionBundleRuntime().summarize(
        provider_result=None,
        gateway_result=None,
        mcp_result=None,
        bundle_ref="live-execution-bundle://wave134/empty",
    )

    assert result.decision == "blocked"
    assert "execution_result_required" in result.blocked_reasons
    assert result.surface_count == 0
    assert result.network_opened is False
    assert result.credential_material_accessed is False


def test_live_execution_bundle_blocks_unsafe_or_secret_echo_result() -> None:
    unsafe_provider = _provider_result().model_copy(
        update={
            "live_production_claimed": True,
            "raw_secret_returned": True,
            "redacted_response": {"content": "token=sk-wave-raw"},
        },
    )

    result = LiveExecutionBundleRuntime().summarize(
        provider_result=unsafe_provider,
        gateway_result=_gateway_result(),
        mcp_result=_mcp_result(),
        bundle_ref="live-execution-bundle://wave134/unsafe",
    )

    assert result.decision == "blocked"
    assert "provider:live_production_claimed" in result.blocked_reasons
    assert "provider:raw_secret_returned" in result.blocked_reasons
    assert "provider:secret_echo_detected" in result.blocked_reasons
    assert result.no_secret_echo is False


def test_cli_and_python_library_live_execution_bundle() -> None:
    runner = CliRunner()
    provider = _provider_result()
    gateway = _gateway_result()
    mcp = _mcp_result()

    completed = runner.invoke(
        app,
        [
            "live-execution-bundle",
            "--provider-result-json",
            provider.model_dump_json(),
            "--gateway-result-json",
            gateway.model_dump_json(),
            "--mcp-result-json",
            mcp.model_dump_json(),
            "--bundle-ref",
            "live-execution-bundle://wave134/cli",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "summarized"
    assert payload["executed_count"] == 3
    assert payload["live_production_claimed"] is False

    library_payload = ZeusAgent().live_execution_bundle(
        provider.to_payload(),
        gateway.to_payload(),
        mcp.to_payload(),
        bundle_ref="live-execution-bundle://wave134/library",
    )
    assert library_payload["decision"] == "summarized"
    assert library_payload["surface_count"] == 3


def _provider_result() -> LiveProviderCredentialedHttpResult:
    return LiveProviderCredentialedHttpResult(
        decision="executed",
        execution_id="provider-execution-wave134",
        release_id="provider-release-wave134",
        injection_id="provider-injection-wave134",
        material_proof_id="material-proof-provider-wave134",
        request_envelope_id="provider-envelope-wave134",
        body_id="provider-body-wave134",
        provider_endpoint="https://api.openai.local/v1/chat/completions",
        transport_endpoint="http://127.0.0.1:7001/v1/chat/completions",
        transport_endpoint_host="127.0.0.1",
        execution_ref="provider-execution-ref-wave134",
        release_ref="provider-release-ref-wave134",
        cleanup_receipt="provider-credentialed-http-client-closed",
        provider_credentialed_http=True,
        sealed_credential_bound=True,
        provider_envelope_bound=True,
        provider_request_body_bound=True,
        local_http_loopback=True,
        provider_invoked=True,
        live_transport_enabled=True,
        execution_allowed=True,
        network_opened=True,
        handler_executed=True,
        credential_material_accessed=True,
        material_released_to_consumer=True,
        status_code=200,
        redacted_response={"choices": [{"message": {"content": "ok"}}]},
    )


def _gateway_result() -> LiveGatewayCredentialedHttpResult:
    return LiveGatewayCredentialedHttpResult(
        decision="executed",
        execution_id="gateway-execution-wave134",
        release_id="gateway-release-wave134",
        injection_id="gateway-injection-wave134",
        material_proof_id="material-proof-gateway-wave134",
        delivery_envelope_id="gateway-envelope-wave134",
        body_id="gateway-body-wave134",
        delivery_endpoint="http://127.0.0.1:7002/deliver",
        delivery_endpoint_host="127.0.0.1",
        execution_ref="gateway-execution-ref-wave134",
        release_ref="gateway-release-ref-wave134",
        cleanup_receipt="gateway-credentialed-http-client-closed",
        gateway_credentialed_http=True,
        sealed_credential_bound=True,
        gateway_envelope_bound=True,
        gateway_delivery_body_bound=True,
        local_http_loopback=True,
        delivery_attempted=True,
        live_transport_enabled=True,
        execution_allowed=True,
        network_opened=True,
        handler_executed=True,
        credential_material_accessed=True,
        material_released_to_consumer=True,
        status_code=200,
        redacted_response={"delivered": True},
    )


def _mcp_result() -> LiveMcpCredentialedHttpResult:
    return LiveMcpCredentialedHttpResult(
        decision="executed",
        execution_id="mcp-execution-wave134",
        release_id="mcp-release-wave134",
        injection_id="mcp-injection-wave134",
        material_proof_id="material-proof-mcp-wave134",
        request_envelope_id="mcp-envelope-wave134",
        body_id="mcp-body-wave134",
        transport_endpoint="http://127.0.0.1:7003/rpc",
        transport_endpoint_host="127.0.0.1",
        execution_ref="mcp-execution-ref-wave134",
        release_ref="mcp-release-ref-wave134",
        cleanup_receipt="mcp-credentialed-http-client-closed",
        mcp_credentialed_http=True,
        sealed_credential_bound=True,
        mcp_envelope_bound=True,
        mcp_request_body_bound=True,
        local_http_loopback=True,
        tool_invoked=True,
        live_transport_enabled=True,
        execution_allowed=True,
        network_opened=True,
        handler_executed=True,
        credential_material_accessed=True,
        material_released_to_consumer=True,
        status_code=200,
        redacted_response={"result": {"ok": True}},
    )
