from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.approval_receipt_runtime import ApprovalReceiptRuntime
from zeus_agent.cli import app
from zeus_agent.live_operator_proof_runtime import LiveOperatorProofRuntime
from zeus_agent.live_production_approval_runtime import LiveProductionApprovalRuntime
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditRuntime
from zeus_agent.live_transport_teardown_runtime import LiveTransportTeardownRuntime
from tests.test_wave111_remote_credential_handoff import _gateway_policy, _mcp_policy, _provider_policy
from tests.test_wave112_remote_executor_preflight import _gateway_handoff, _mcp_handoff, _provider_handoff
from tests.test_wave113_provider_external_transport import _provider_preflight, _provider_request
from tests.test_wave117_provider_owned_client_transport import _FakeProviderClient, _receipt as _provider_receipt
from tests.test_wave118_gateway_owned_client_transport import _FakeGatewayClient, _receipt as _gateway_receipt
from tests.test_wave114_gateway_external_transport import _gateway_preflight
from tests.test_wave119_mcp_owned_client_transport import _FakeMcpClient, _receipt as _mcp_receipt
from tests.test_wave103_gateway_loopback_transport import _gateway_envelope
from tests.test_wave115_mcp_external_transport import _mcp_preflight, _mcp_request
from zeus_agent.live_provider_owned_client_transport_runtime import LiveProviderOwnedClientTransportRuntime
from zeus_agent.live_gateway_owned_client_transport_runtime import LiveGatewayOwnedClientTransportRuntime
from zeus_agent.live_mcp_owned_client_transport_runtime import LiveMcpOwnedClientTransportRuntime


def test_live_production_approval_accepts_owned_transports_for_all_surfaces(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")

    provider = _provider_bundle(tmp_path)
    gateway = _gateway_bundle(tmp_path)
    mcp = _mcp_bundle(tmp_path)

    for adapter_kind, bundle in (("provider", provider), ("gateway", gateway), ("mcp", mcp)):
        result = LiveProductionApprovalRuntime().approve(
            adapter_kind=adapter_kind,
            execution=bundle["execution"],
            audit=bundle["audit"],
            teardown=bundle["teardown"],
            approval_receipt=_approval(adapter_kind),
            operator_proof=_proof(adapter_kind),
            production_ref="production-approval://wave120/{0}".format(adapter_kind),
        )

        assert result.decision == "production_approval_ready"
        assert result.production_claim_authorized is True
        assert result.execution_bound is True
        assert result.audit_bound is True
        assert result.teardown_bound is True
        assert result.approval_receipt_bound is True
        assert result.operator_proof_bound is True
        assert result.live_production_claimed is False


def test_live_production_approval_blocks_wrong_receipt_scope(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    bundle = _provider_bundle(tmp_path)

    result = LiveProductionApprovalRuntime().approve(
        adapter_kind="provider",
        execution=bundle["execution"],
        audit=bundle["audit"],
        teardown=bundle["teardown"],
        approval_receipt=_approval("gateway"),
        operator_proof=_proof("provider"),
        production_ref="production-approval://wave120/provider",
    )

    assert result.decision == "blocked"
    assert "approval_receipt_scope_mismatch" in result.blocked_reasons
    assert result.production_claim_authorized is False


def test_live_production_approval_blocks_execution_self_claim(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    bundle = _mcp_bundle(tmp_path)
    execution = bundle["execution"].model_copy(update={"live_production_claimed": True})

    result = LiveProductionApprovalRuntime().approve(
        adapter_kind="mcp",
        execution=execution,
        audit=bundle["audit"],
        teardown=bundle["teardown"],
        approval_receipt=_approval("mcp"),
        operator_proof=_proof("mcp"),
        production_ref="production-approval://wave120/mcp",
    )

    assert result.decision == "blocked"
    assert "execution_self_production_claim_detected" in result.blocked_reasons


def test_cli_and_python_library_live_production_approval(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    bundle = _provider_bundle(tmp_path)
    receipt = _approval("provider")
    proof = _proof("provider")

    completed = CliRunner().invoke(
        app,
        [
            "live-production-approval",
            "--adapter-kind",
            "provider",
            "--execution-json",
            bundle["execution"].model_dump_json(),
            "--audit-json",
            bundle["audit"].model_dump_json(),
            "--teardown-json",
            bundle["teardown"].model_dump_json(),
            "--approval-receipt-json",
            receipt.model_dump_json(),
            "--operator-proof-json",
            proof.model_dump_json(),
            "--production-ref",
            "production-approval://wave120/provider",
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).live_production_approval(
        adapter_kind="provider",
        execution=bundle["execution"].to_payload(),
        audit=bundle["audit"].to_payload(),
        teardown=bundle["teardown"].to_payload(),
        approval_receipt=receipt.to_payload(),
        operator_proof=proof.to_payload(),
        production_ref="production-approval://wave120/provider-library",
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "production_approval_ready"
    assert payload["production_claim_authorized"] is True
    assert payload["live_production_claimed"] is False
    assert library_payload["decision"] == "production_approval_ready"


def _provider_bundle(home: Path):
    execution = LiveProviderOwnedClientTransportRuntime().execute(
        policy=_provider_policy(),
        preflight=_provider_preflight(),
        handoff=_provider_handoff(),
        provider_envelope=_provider_request(),
        client=_FakeProviderClient(_provider_receipt()),
        execution_ref="provider-owned-client://wave120/provider",
    )
    return _bundle(home, "provider", _provider_policy(), _provider_preflight(), execution)


def _gateway_bundle(home: Path):
    execution = LiveGatewayOwnedClientTransportRuntime().execute(
        policy=_gateway_policy(),
        preflight=_gateway_preflight(),
        handoff=_gateway_handoff(),
        gateway_envelope=_gateway_envelope(),
        client=_FakeGatewayClient(_gateway_receipt()),
        execution_ref="gateway-owned-client://wave120/gateway",
    )
    return _bundle(home, "gateway", _gateway_policy(), _gateway_preflight(), execution)


def _mcp_bundle(home: Path):
    execution = LiveMcpOwnedClientTransportRuntime().execute(
        policy=_mcp_policy(),
        preflight=_mcp_preflight(),
        handoff=_mcp_handoff(),
        mcp_envelope=_mcp_request(),
        client=_FakeMcpClient(_mcp_receipt()),
        execution_ref="mcp-owned-client://wave120/mcp",
    )
    return _bundle(home, "mcp", _mcp_policy(), _mcp_preflight(), execution)


def _bundle(home: Path, adapter_kind: str, policy, preflight, execution):
    audit = LiveTransportAuditRuntime().audit(
        adapter_kind=adapter_kind,
        execution=execution,
        audit_ref="live-audit://wave120/{0}".format(adapter_kind),
    )
    teardown = LiveTransportTeardownRuntime().record(
        home=home,
        adapter_kind=adapter_kind,
        policy=policy,
        preflight=preflight,
        execution=execution,
        audit=audit,
        teardown_ref=policy.teardown_ref or "",
    )
    return {"execution": execution, "audit": audit, "teardown": teardown}


def _approval(adapter_kind: str):
    approval_id, capability_id = {
        "provider": ("provider-live", "provider.external.generate"),
        "gateway": ("external-delivery", "gateway.webhook.dispatch"),
        "mcp": ("mcp-live", "mcp.echo"),
    }[adapter_kind]
    return ApprovalReceiptRuntime().record(
        approval_id=approval_id,
        principal_id="wave120.principal.{0}".format(adapter_kind),
        objective_id="wave120.objective.production",
        capability_id=capability_id,
    )


def _proof(adapter_kind: str):
    risks = {
        "provider": ("network", "credential_material_access", "external_provider_inference", "live_transport", "production_claim"),
        "gateway": ("network", "credential_material_access", "external_delivery", "live_transport", "production_claim"),
        "mcp": ("network", "credential_material_access", "mcp_remote_tool", "live_transport", "production_claim"),
    }[adapter_kind]
    return LiveOperatorProofRuntime().record(
        proof_id="wave120.proof.{0}".format(adapter_kind),
        operator_id="wave120.operator",
        execution_plan_id="wave120.execution.{0}".format(adapter_kind),
        proof_ref="operator-proof://wave120/{0}".format(adapter_kind),
        reviewed_risks=risks,
    )
