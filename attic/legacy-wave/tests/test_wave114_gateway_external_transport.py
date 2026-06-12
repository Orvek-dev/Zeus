from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_gateway_external_transport_runtime import (
    LiveGatewayExternalClientResult,
    LiveGatewayExternalTransportRuntime,
)
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightRuntime
from zeus_agent.live_response_redaction_runtime import LiveResponseRedactionRuntime
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditRuntime
from tests.test_wave103_gateway_loopback_transport import _gateway_envelope
from tests.test_wave111_remote_credential_handoff import _gateway_policy
from tests.test_wave112_remote_executor_preflight import _gateway_handoff


def test_gateway_external_transport_executes_with_controlled_audit_and_redaction(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")

    result = LiveGatewayExternalTransportRuntime().execute(
        policy=_gateway_policy(),
        preflight=_gateway_preflight(),
        gateway_envelope=_gateway_envelope(),
        client_result=_client_result(),
        execution_ref="gateway-external://wave114/slack",
    )
    audit = LiveTransportAuditRuntime().audit(
        adapter_kind="gateway",
        execution=result,
        audit_ref="live-audit://wave114/gateway-external",
    )
    redaction = LiveResponseRedactionRuntime().redact(
        audit=audit,
        response_payload=_client_result().response_payload,
        response_ref="live-response://wave114/gateway-external",
    )

    assert result.decision == "executed"
    assert result.policy_bound is True
    assert result.remote_executor_preflight_bound is True
    assert result.gateway_envelope_bound is True
    assert result.delivery_attempted is True
    assert result.network_opened is True
    assert result.non_loopback_network_opened is True
    assert result.external_delivery_opened is True
    assert result.controlled_external_side_effects is True
    assert result.credential_material_accessed is False
    assert result.raw_secret_returned is False
    assert result.cleanup_receipt == "gateway-external-http-client-closed"
    assert "xoxb-" + "wave114" not in json.dumps(result.to_payload())
    assert audit.decision == "audit_ready"
    assert audit.controlled_external_side_effects is True
    assert audit.external_side_effects_absent is False
    assert redaction.decision == "redacted"
    assert redaction.no_secret_echo is True
    assert result.live_production_claimed is False


def test_gateway_external_transport_blocks_target_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    envelope = _gateway_envelope().model_copy(update={"target": "discord://ops"})

    result = LiveGatewayExternalTransportRuntime().execute(
        policy=_gateway_policy(),
        preflight=_gateway_preflight(),
        gateway_envelope=envelope,
        client_result=_client_result(),
        execution_ref="gateway-external://wave114/mismatch",
    )

    assert result.decision == "blocked"
    assert "gateway_remote_target_mismatch" in result.blocked_reasons
    assert "gateway_preflight_target_mismatch" in result.blocked_reasons
    assert result.network_opened is False
    assert result.external_delivery_opened is False


def test_gateway_external_transport_blocks_unconfirmed_delivery(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    client_result = _client_result().model_copy(update={"external_delivery_opened": False})

    result = LiveGatewayExternalTransportRuntime().execute(
        policy=_gateway_policy(),
        preflight=_gateway_preflight(),
        gateway_envelope=_gateway_envelope(),
        client_result=client_result,
        execution_ref="gateway-external://wave114/client-block",
    )

    assert result.decision == "blocked"
    assert "gateway_external_delivery_not_confirmed" in result.blocked_reasons
    assert result.network_opened is False
    assert result.live_transport_enabled is False


def test_cli_and_python_library_gateway_external_transport(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    policy = _gateway_policy()
    preflight = _gateway_preflight()
    envelope = _gateway_envelope()
    client_result = _client_result()

    completed = CliRunner().invoke(
        app,
        [
            "live-gateway-external-transport",
            "--policy-json",
            policy.model_dump_json(),
            "--preflight-json",
            preflight.model_dump_json(),
            "--gateway-envelope-json",
            envelope.model_dump_json(),
            "--client-result-json",
            client_result.model_dump_json(),
            "--execution-ref",
            "gateway-external://wave114/slack",
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_gateway_external_transport(
        policy.to_payload(),
        preflight.to_payload(),
        envelope.to_payload(),
        client_result.model_dump(mode="json"),
        execution_ref="gateway-external://wave114/slack-library",
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "executed"
    assert payload["network_opened"] is True
    assert payload["non_loopback_network_opened"] is True
    assert payload["external_delivery_opened"] is True
    assert payload["controlled_external_side_effects"] is True
    assert payload["live_production_claimed"] is False
    assert library_payload["decision"] == "executed"


def _gateway_preflight():
    policy = _gateway_policy()
    return LiveRemoteExecutorPreflightRuntime().plan(
        policy=policy,
        handoff=_gateway_handoff(),
        executor_kind="gateway",
        executor_ref="remote-executor://wave114/gateway",
        idempotency_key="wave114-gateway-external",
        teardown_ref=policy.teardown_ref or "",
        timeout_ms=1500,
        retry_attempts=1,
    )


def _client_result() -> LiveGatewayExternalClientResult:
    return LiveGatewayExternalClientResult(
        status_code=200,
        latency_ms=52,
        response_payload={
            "ok": True,
            "channel": "ops",
            "debug": "token=xoxb-" + "wave114",
        },
        network_opened=True,
        non_loopback_network_opened=True,
        external_delivery_opened=True,
        cleanup_receipt="gateway-external-http-client-closed",
    )
