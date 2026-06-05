from __future__ import annotations

import json
from datetime import datetime, timezone

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_transport_lease_runtime import LiveTransportLeaseRuntime
from zeus_agent.runtime_lease import RuntimeLease
from tests.test_wave88_live_gateway_execution import _gateway_readiness


def test_live_transport_lease_blocks_without_readiness() -> None:
    result = LiveTransportLeaseRuntime().bind(
        readiness=None,
        lease=_gateway_lease(),
        runtime_kind="gateway",
        capability_id="gateway.slack.dispatch",
        credential_scope="external.gateway.readonly",
        network_host="gateway.local",
        budget_required=1,
        evidence_target="mneme.wave89.live_transport_lease",
        now=_now(),
    )

    assert result.decision == "blocked"
    assert "execution_readiness_required" in result.blocked_reasons
    assert result.transport_lease_bound is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_live_transport_lease_binds_endpoint_without_opening_network() -> None:
    result = LiveTransportLeaseRuntime().bind(
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

    assert result.decision == "bound"
    assert result.transport_lease_bound is True
    assert result.lease_authorized is True
    assert result.network_host == "gateway.local"
    assert result.credential_scope_label == "external.gateway.readonly"
    assert result.live_network_requested is True
    assert result.live_transport_enabled is False
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.external_delivery_opened is False
    assert result.live_production_claimed is False


def test_live_transport_lease_blocks_endpoint_widening() -> None:
    result = LiveTransportLeaseRuntime().bind(
        readiness=_gateway_readiness(),
        lease=_gateway_lease(),
        runtime_kind="gateway",
        capability_id="gateway.slack.dispatch",
        credential_scope="external.gateway.readonly",
        network_host="evil.local",
        budget_required=1,
        evidence_target="mneme.wave89.live_transport_lease",
        now=_now(),
    )

    assert result.decision == "blocked"
    assert "runtime_lease_live_network_without_scope" in result.blocked_reasons
    assert result.lease_authorized is False
    assert result.transport_lease_bound is False
    assert result.network_opened is False


def test_cli_and_python_library_live_transport_lease() -> None:
    readiness = _gateway_readiness()
    lease = _gateway_lease()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-transport-lease",
            "--readiness-json",
            readiness.model_dump_json(),
            "--lease-json",
            lease.model_dump_json(),
            "--runtime-kind",
            "gateway",
            "--capability-id",
            "gateway.slack.dispatch",
            "--credential-scope",
            "external.gateway.readonly",
            "--network-host",
            "gateway.local",
            "--budget-required",
            "1",
            "--evidence-target",
            "mneme.wave89.live_transport_lease",
            "--now",
            "2026-06-04T12:00:00+00:00",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "bound"
    assert payload["network_opened"] is False

    library_payload = ZeusAgent().live_transport_lease(
        readiness.to_payload(),
        lease.model_dump(mode="json"),
        runtime_kind="gateway",
        capability_id="gateway.slack.dispatch",
        credential_scope="external.gateway.readonly",
        network_host="gateway.local",
        budget_required=1,
        evidence_target="mneme.wave89.live_transport_lease",
        now=_now(),
    )
    assert library_payload["decision"] == "bound"
    assert library_payload["transport_lease_bound"] is True


def _gateway_lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave89.lease.gateway",
        objective_id="wave89.objective.live",
        principal_id="wave89.principal.operator",
        run_id="wave89.run.live",
        allowed_capabilities=("gateway.slack.dispatch",),
        credential_scopes=("external.gateway.readonly",),
        network_hosts=("gateway.local",),
        budget_limit=100,
        evidence_target="mneme.wave89.live_transport_lease",
        live_transport_allowed=True,
        issued_at=datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 6, 0, 0, tzinfo=timezone.utc),
    )


def _now() -> datetime:
    return datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
