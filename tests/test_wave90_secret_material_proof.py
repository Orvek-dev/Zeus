from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialRuntime
from zeus_agent.live_transport_lease_runtime import LiveTransportLeaseRuntime
from tests.test_wave88_live_gateway_execution import _gateway_readiness
from tests.test_wave89_live_transport_lease import _gateway_lease, _now


def test_secret_material_check_blocks_without_transport_lease() -> None:
    result = LiveSecretMaterialRuntime().check(
        transport_lease=None,
        secret_ref="env://ZEUS_W90_GATEWAY_TOKEN",
        allow_material_access=True,
    )

    assert result.decision == "blocked"
    assert "transport_lease_required" in result.blocked_reasons
    assert result.credential_material_accessed is False
    assert result.material_released is False
    assert result.live_production_claimed is False


def test_secret_material_check_requires_explicit_material_access() -> None:
    result = LiveSecretMaterialRuntime().check(
        transport_lease=_transport_lease(),
        secret_ref="env://ZEUS_W90_GATEWAY_TOKEN",
        allow_material_access=False,
    )

    assert result.decision == "blocked"
    assert "secret_material_access_not_approved" in result.blocked_reasons
    assert result.env_value_read is False
    assert result.credential_material_accessed is False


def test_secret_material_check_reads_env_availability_without_echo(monkeypatch) -> None:
    material = "credential-" + "material-value"
    monkeypatch.setenv("ZEUS_W90_GATEWAY_TOKEN", material)

    result = LiveSecretMaterialRuntime().check(
        transport_lease=_transport_lease(),
        secret_ref="env://ZEUS_W90_GATEWAY_TOKEN",
        allow_material_access=True,
    )

    payload = result.to_payload()
    assert result.decision == "available"
    assert result.material_available is True
    assert result.credential_material_accessed is True
    assert result.env_value_read is True
    assert result.material_released is False
    assert result.raw_secret_returned is False
    assert result.no_secret_echo is True
    assert material not in json.dumps(payload)


def test_cli_and_python_library_secret_material_check(monkeypatch) -> None:
    material = "credential-" + "material-value"
    monkeypatch.setenv("ZEUS_W90_GATEWAY_TOKEN", material)
    transport_lease = _transport_lease()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-secret-material-check",
            "--transport-lease-json",
            transport_lease.model_dump_json(),
            "--secret-ref",
            "env://ZEUS_W90_GATEWAY_TOKEN",
            "--allow-material-access",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "available"
    assert payload["raw_secret_returned"] is False
    assert material not in completed.stdout

    library_payload = ZeusAgent().live_secret_material_check(
        transport_lease.to_payload(),
        secret_ref="env://ZEUS_W90_GATEWAY_TOKEN",
        allow_material_access=True,
    )
    assert library_payload["decision"] == "available"
    assert library_payload["credential_material_accessed"] is True


def _transport_lease():
    return LiveTransportLeaseRuntime().bind(
        readiness=_gateway_readiness(),
        lease=_gateway_lease(),
        runtime_kind="gateway",
        capability_id="gateway.slack.dispatch",
        credential_scope="external.gateway.readonly",
        network_host="gateway.local",
        budget_required=1,
        evidence_target="mneme.wave89.live_transport_lease",
        now=_now(),
    )
