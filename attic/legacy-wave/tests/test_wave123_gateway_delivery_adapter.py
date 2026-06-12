from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionRuntime
from zeus_agent.live_gateway_delivery_adapter_runtime import (
    LiveGatewayDeliveryAdapterReceipt,
    LiveGatewayDeliveryAdapterRequest,
    LiveGatewayDeliveryAdapterRuntime,
)
from zeus_agent.live_production_approval_runtime import LiveProductionApprovalRuntime
from zeus_agent.live_production_claim_runtime import LiveProductionClaimRuntime
from zeus_agent.live_response_redaction_runtime import LiveResponseRedactionRuntime
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditRuntime
from zeus_agent.live_transport_teardown_runtime import LiveTransportTeardownRuntime
from tests.test_wave103_gateway_loopback_transport import _gateway_envelope
from tests.test_wave111_remote_credential_handoff import _gateway_policy
from tests.test_wave112_remote_executor_preflight import _gateway_handoff
from tests.test_wave114_gateway_external_transport import _gateway_preflight
from tests.test_wave120_live_production_approval import _approval, _gateway_bundle, _proof
from tests.test_wave121_live_production_claim import _production_approval
from tests.test_wave92_gateway_delivery_envelope import _secret_material as _gateway_secret_material


class _FakeGatewayDeliveryClient:
    def __init__(self, receipt: LiveGatewayDeliveryAdapterReceipt) -> None:
        self.receipt = receipt
        self.requests: list[LiveGatewayDeliveryAdapterRequest] = []

    def deliver(self, request: LiveGatewayDeliveryAdapterRequest) -> LiveGatewayDeliveryAdapterReceipt:
        self.requests.append(request)
        return self.receipt


def test_gateway_delivery_adapter_executes_only_after_claim(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    client = _FakeGatewayDeliveryClient(_receipt())
    context = _gateway_context(tmp_path)

    result = LiveGatewayDeliveryAdapterRuntime().execute(
        claim=context["claim"],
        policy=context["policy"],
        preflight=context["preflight"],
        handoff=context["handoff"],
        credential_injection=context["injection"],
        gateway_envelope=_gateway_envelope(),
        client=client,
        execution_ref="gateway-delivery://wave123/slack",
    )
    audit = LiveTransportAuditRuntime().audit(
        adapter_kind="gateway",
        execution=result,
        audit_ref="live-audit://wave123/gateway-delivery",
    )
    redaction = LiveResponseRedactionRuntime().redact(
        audit=audit,
        response_payload=_receipt().response_payload,
        response_ref="live-response://wave123/gateway-delivery",
    )
    teardown = LiveTransportTeardownRuntime().record(
        home=tmp_path,
        adapter_kind="gateway",
        policy=context["policy"],
        preflight=context["preflight"],
        execution=result,
        audit=audit,
        teardown_ref=context["policy"].teardown_ref or "",
    )

    assert result.decision == "executed"
    assert result.gateway_delivery_adapter is True
    assert result.production_claim_bound is True
    assert result.credential_injection_bound is True
    assert result.request_constructed is True
    assert result.delivery_attempted is True
    assert result.external_delivery_opened is True
    assert result.controlled_external_side_effects is True
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False
    assert client.requests[0].production_claim_id == context["claim"].claim_id
    assert client.requests[0].header_value_ref == context["injection"].header_value_ref
    assert "gateway-" + "material-value" not in json.dumps(client.requests[0].to_payload())
    assert audit.decision == "audit_ready"
    assert redaction.decision == "redacted"
    assert teardown.decision == "teardown_recorded"


def test_gateway_delivery_adapter_blocks_without_claim(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")

    result = LiveGatewayDeliveryAdapterRuntime().execute(
        claim=None,
        policy=_gateway_policy(),
        preflight=None,
        handoff=_gateway_handoff(),
        credential_injection=None,
        gateway_envelope=_gateway_envelope(),
        client=_FakeGatewayDeliveryClient(_receipt()),
        execution_ref="gateway-delivery://wave123/no-claim",
    )

    assert result.decision == "blocked"
    assert "production_claim_required" in result.blocked_reasons
    assert result.delivery_attempted is False
    assert result.external_delivery_opened is False


def test_gateway_delivery_adapter_audit_requires_claim_binding(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    context = _gateway_context(tmp_path)
    result = LiveGatewayDeliveryAdapterRuntime().execute(
        claim=context["claim"],
        policy=context["policy"],
        preflight=context["preflight"],
        handoff=context["handoff"],
        credential_injection=context["injection"],
        gateway_envelope=_gateway_envelope(),
        client=_FakeGatewayDeliveryClient(_receipt()),
        execution_ref="gateway-delivery://wave123/no-claim-bound",
    ).model_copy(update={"production_claim_bound": False})

    audit = LiveTransportAuditRuntime().audit(
        adapter_kind="gateway",
        execution=result,
        audit_ref="live-audit://wave123/no-claim-bound",
    )

    assert audit.decision == "blocked"
    assert "gateway_production_claim_not_bound" in audit.blocked_reasons


def test_gateway_delivery_adapter_blocks_wrong_claim_adapter(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    claim = _provider_claim(tmp_path)
    context = _gateway_context(tmp_path)

    result = LiveGatewayDeliveryAdapterRuntime().execute(
        claim=claim,
        policy=context["policy"],
        preflight=context["preflight"],
        handoff=context["handoff"],
        credential_injection=context["injection"],
        gateway_envelope=_gateway_envelope(),
        client=_FakeGatewayDeliveryClient(_receipt()),
        execution_ref="gateway-delivery://wave123/wrong-claim",
    )

    assert result.decision == "blocked"
    assert "gateway_production_claim_mismatch" in result.blocked_reasons
    assert result.network_opened is False


def test_cli_and_python_library_gateway_delivery_adapter(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    context = _gateway_context(tmp_path)
    claim = context["claim"]
    policy = context["policy"]
    preflight = context["preflight"]
    handoff = context["handoff"]
    injection = context["injection"]
    envelope = _gateway_envelope()
    receipt = _receipt()

    completed = CliRunner().invoke(
        app,
        [
            "live-gateway-delivery-adapter",
            "--claim-json",
            claim.model_dump_json(),
            "--policy-json",
            policy.model_dump_json(),
            "--preflight-json",
            preflight.model_dump_json(),
            "--handoff-json",
            handoff.model_dump_json(),
            "--credential-injection-json",
            injection.model_dump_json(),
            "--gateway-envelope-json",
            envelope.model_dump_json(),
            "--client-receipt-json",
            receipt.model_dump_json(),
            "--execution-ref",
            "gateway-delivery://wave123/slack",
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).live_gateway_delivery_adapter(
        claim.to_payload(),
        policy.to_payload(),
        preflight.to_payload(),
        handoff.to_payload(),
        injection.to_payload(),
        envelope.to_payload(),
        receipt.model_dump(mode="json"),
        execution_ref="gateway-delivery://wave123/slack-library",
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "executed"
    assert payload["gateway_delivery_adapter"] is True
    assert payload["production_claim_bound"] is True
    assert payload["credential_injection_bound"] is True
    assert payload["external_delivery_opened"] is True
    assert payload["live_production_claimed"] is False
    assert library_payload["decision"] == "executed"


def _gateway_context(tmp_path: Path):
    claim = _gateway_claim(tmp_path)
    policy = _gateway_policy()
    preflight = _gateway_preflight()
    handoff = _gateway_handoff()
    injection = LiveCredentialInjectionRuntime().prepare(
        adapter_kind="gateway",
        claim=claim,
        policy=policy,
        preflight=preflight,
        handoff=handoff,
        secret_material=_gateway_secret_material(),
        injection_ref="credential-injection://wave123/gateway",
    )
    return {"claim": claim, "policy": policy, "preflight": preflight, "handoff": handoff, "injection": injection}


def _gateway_claim(tmp_path: Path):
    bundle = _gateway_bundle(tmp_path)
    approval = LiveProductionApprovalRuntime().approve(
        adapter_kind="gateway",
        execution=bundle["execution"],
        audit=bundle["audit"],
        teardown=bundle["teardown"],
        approval_receipt=_approval("gateway"),
        operator_proof=_proof("gateway"),
        production_ref="production-approval://wave123/gateway",
    )
    return LiveProductionClaimRuntime().record(
        home=tmp_path,
        approval=approval,
        claim_ref="production-claim://wave123/gateway",
    )


def _provider_claim(tmp_path: Path):
    approval = _production_approval(tmp_path, "provider")
    return LiveProductionClaimRuntime().record(
        home=tmp_path,
        approval=approval,
        claim_ref="production-claim://wave123/provider",
    )


def _receipt() -> LiveGatewayDeliveryAdapterReceipt:
    return LiveGatewayDeliveryAdapterReceipt(
        status_code=200,
        latency_ms=53,
        response_payload={"ok": True, "channel": "ops", "debug": "token=xoxb-" + "wave123"},
        network_opened=True,
        non_loopback_network_opened=True,
        external_delivery_opened=True,
        cleanup_receipt="gateway-delivery-adapter-client-closed",
    )
