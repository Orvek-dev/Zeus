from __future__ import annotations

import json
from datetime import datetime, timezone

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_provider_request_runtime import LiveProviderRequestRuntime
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialRuntime
from zeus_agent.live_transport_lease_runtime import LiveTransportLeaseRuntime
from zeus_agent.runtime_lease import RuntimeLease
from tests.test_wave86_live_provider_execution import _provider_readiness


def test_provider_request_envelope_blocks_without_transport_lease() -> None:
    result = LiveProviderRequestRuntime().prepare(
        transport_lease=None,
        secret_material=None,
        provider_kind="openai_compatible",
        model_id="gpt-test",
        endpoint="https://api.openai.local/v1/chat/completions",
        message="summarize local state",
    )

    assert result.decision == "blocked"
    assert "transport_lease_required" in result.blocked_reasons
    assert result.provider_invoked is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_provider_request_envelope_prepares_external_provider_without_network(monkeypatch) -> None:
    material = "provider-" + "material-value"
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", material)

    result = LiveProviderRequestRuntime().prepare(
        transport_lease=_provider_transport_lease(),
        secret_material=_secret_material(),
        provider_kind="openai_compatible",
        model_id="gpt-test",
        endpoint="https://api.openai.local/v1/chat/completions",
        message="summarize local state",
    )

    payload = result.to_payload()
    assert result.decision == "prepared"
    assert result.request_prepared is True
    assert result.secret_material_verified is True
    assert result.endpoint_host == "api.openai.local"
    assert result.provider_invoked is False
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.raw_secret_returned is False
    assert result.live_production_claimed is False
    assert material not in json.dumps(payload)


def test_provider_request_envelope_blocks_endpoint_outside_transport_lease(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")

    result = LiveProviderRequestRuntime().prepare(
        transport_lease=_provider_transport_lease(),
        secret_material=_secret_material(),
        provider_kind="openai_compatible",
        model_id="gpt-test",
        endpoint="https://evil.local/v1/chat/completions",
        message="summarize local state",
    )

    assert result.decision == "blocked"
    assert "provider_endpoint_not_lease_bound" in result.blocked_reasons
    assert result.request_prepared is False
    assert result.network_opened is False


def test_cli_and_python_library_provider_request_envelope(monkeypatch) -> None:
    material = "provider-" + "material-value"
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", material)
    transport_lease = _provider_transport_lease()
    secret_material = _secret_material()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-provider-request-envelope",
            "--transport-lease-json",
            transport_lease.model_dump_json(),
            "--secret-material-json",
            secret_material.model_dump_json(),
            "--provider-kind",
            "openai_compatible",
            "--model-id",
            "gpt-test",
            "--endpoint",
            "https://api.openai.local/v1/chat/completions",
            "--message",
            "summarize local state",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "prepared"
    assert payload["network_opened"] is False
    assert material not in completed.stdout

    library_payload = ZeusAgent().live_provider_request_envelope(
        transport_lease.to_payload(),
        secret_material.to_payload(),
        provider_kind="openai_compatible",
        model_id="gpt-test",
        endpoint="https://api.openai.local/v1/chat/completions",
        message="summarize local state",
    )
    assert library_payload["decision"] == "prepared"
    assert library_payload["provider_invoked"] is False


def _provider_transport_lease():
    return LiveTransportLeaseRuntime().bind(
        readiness=_provider_readiness(),
        lease=_provider_lease(),
        runtime_kind="provider",
        capability_id="provider.external.generate",
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
        budget_required=1,
        evidence_target="mneme.wave91.provider_request",
        now=_now(),
    )


def _secret_material():
    return LiveSecretMaterialRuntime().check(
        transport_lease=_provider_transport_lease(),
        secret_ref="env://ZEUS_W91_OPENAI_KEY",
        allow_material_access=True,
    )


def _provider_lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave91.lease.provider",
        objective_id="wave91.objective.live",
        principal_id="wave91.principal.operator",
        run_id="wave91.run.live",
        allowed_capabilities=("provider.external.generate",),
        credential_scopes=("external.openai.readonly",),
        network_hosts=("api.openai.local",),
        budget_limit=100,
        evidence_target="mneme.wave91.provider_request",
        live_transport_allowed=True,
        issued_at=datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 6, 0, 0, tzinfo=timezone.utc),
    )


def _now() -> datetime:
    return datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
