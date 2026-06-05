from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditRuntime
from zeus_agent.live_transport_teardown_runtime import LiveTransportTeardownRuntime
from tests.test_wave113_provider_external_transport import _client_result as _provider_client
from tests.test_wave113_provider_external_transport import _provider_policy, _provider_preflight, _provider_request
from tests.test_wave114_gateway_external_transport import _client_result as _gateway_client
from tests.test_wave114_gateway_external_transport import _gateway_preflight
from tests.test_wave103_gateway_loopback_transport import _gateway_envelope
from tests.test_wave111_remote_credential_handoff import _gateway_policy
from tests.test_wave115_mcp_external_transport import _client_result as _mcp_client
from tests.test_wave115_mcp_external_transport import _mcp_preflight, _mcp_request
from tests.test_wave111_remote_credential_handoff import _mcp_policy
from zeus_agent.live_provider_external_transport_runtime import LiveProviderExternalTransportRuntime
from zeus_agent.live_gateway_external_transport_runtime import LiveGatewayExternalTransportRuntime
from zeus_agent.live_mcp_external_transport_runtime import LiveMcpExternalTransportRuntime


def test_transport_teardown_records_provider_gateway_and_mcp_idempotently(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")

    provider = _provider_execution()
    gateway = _gateway_execution()
    mcp = _mcp_execution()
    runtime = LiveTransportTeardownRuntime()

    provider_record = runtime.record(
        home=tmp_path,
        adapter_kind="provider",
        policy=_provider_policy(),
        preflight=_provider_preflight(),
        execution=provider,
        audit=_audit("provider", provider),
        teardown_ref=_provider_policy().teardown_ref or "",
    )
    gateway_record = runtime.record(
        home=tmp_path,
        adapter_kind="gateway",
        policy=_gateway_policy(),
        preflight=_gateway_preflight(),
        execution=gateway,
        audit=_audit("gateway", gateway),
        teardown_ref=_gateway_policy().teardown_ref or "",
    )
    mcp_record = runtime.record(
        home=tmp_path,
        adapter_kind="mcp",
        policy=_mcp_policy(),
        preflight=_mcp_preflight(),
        execution=mcp,
        audit=_audit("mcp", mcp),
        teardown_ref=_mcp_policy().teardown_ref or "",
    )
    repeated = runtime.record(
        home=tmp_path,
        adapter_kind="provider",
        policy=_provider_policy(),
        preflight=_provider_preflight(),
        execution=provider,
        audit=_audit("provider", provider),
        teardown_ref=_provider_policy().teardown_ref or "",
    )

    rows = (tmp_path / "live_transport_teardown.jsonl").read_text(encoding="utf-8").splitlines()
    assert provider_record.decision == "teardown_recorded"
    assert gateway_record.decision == "teardown_recorded"
    assert mcp_record.decision == "teardown_recorded"
    assert repeated.duplicate is True
    assert len(rows) == 3
    assert all(json.loads(row)["live_production_claimed"] is False for row in rows)


def test_transport_teardown_blocks_policy_teardown_mismatch(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    execution = _provider_execution()

    result = LiveTransportTeardownRuntime().record(
        home=tmp_path,
        adapter_kind="provider",
        policy=_provider_policy(),
        preflight=_provider_preflight(),
        execution=execution,
        audit=_audit("provider", execution),
        teardown_ref="teardown://wrong",
    )

    assert result.decision == "blocked"
    assert "teardown_ref_policy_mismatch" in result.blocked_reasons
    assert result.ledger_recorded is False
    assert not (tmp_path / "live_transport_teardown.jsonl").exists()


def test_cli_and_python_library_transport_teardown(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    policy = _provider_policy()
    preflight = _provider_preflight()
    execution = _provider_execution()
    audit = _audit("provider", execution)

    completed = CliRunner().invoke(
        app,
        [
            "live-transport-teardown-record",
            "--home",
            str(tmp_path),
            "--adapter-kind",
            "provider",
            "--policy-json",
            policy.model_dump_json(),
            "--preflight-json",
            preflight.model_dump_json(),
            "--execution-json",
            execution.model_dump_json(),
            "--audit-json",
            audit.model_dump_json(),
            "--teardown-ref",
            policy.teardown_ref or "",
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).live_transport_teardown_record(
        adapter_kind="provider",
        policy=policy.to_payload(),
        preflight=preflight.to_payload(),
        execution=execution.to_payload(),
        audit=audit.to_payload(),
        teardown_ref=policy.teardown_ref or "",
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "teardown_recorded"
    assert payload["ledger_recorded"] is True
    assert payload["live_production_claimed"] is False
    assert library_payload["decision"] == "teardown_recorded"


def _provider_execution():
    return LiveProviderExternalTransportRuntime().execute(
        policy=_provider_policy(),
        preflight=_provider_preflight(),
        provider_envelope=_provider_request(),
        client_result=_provider_client(),
        execution_ref="provider-external://wave116/provider",
    )


def _gateway_execution():
    return LiveGatewayExternalTransportRuntime().execute(
        policy=_gateway_policy(),
        preflight=_gateway_preflight(),
        gateway_envelope=_gateway_envelope(),
        client_result=_gateway_client(),
        execution_ref="gateway-external://wave116/gateway",
    )


def _mcp_execution():
    return LiveMcpExternalTransportRuntime().execute(
        policy=_mcp_policy(),
        preflight=_mcp_preflight(),
        mcp_envelope=_mcp_request(),
        client_result=_mcp_client(),
        execution_ref="mcp-external://wave116/mcp",
    )


def _audit(adapter_kind: str, execution):
    return LiveTransportAuditRuntime().audit(
        adapter_kind=adapter_kind,
        execution=execution,
        audit_ref="live-audit://wave116/{0}".format(adapter_kind),
    )
