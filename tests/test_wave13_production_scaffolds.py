from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from zeus_agent.gateway_runtime.local_gateway import (
    GatewayDraftRequest,
    create_gateway_draft,
    record_api_draft_execution,
)
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.wave13_production_scenarios import (
    wave13_blocks_payload,
    wave13_production_payload,
)


def test_wave13_production_payload_creates_local_scaffolds_without_live_transport(
    tmp_path: Path,
) -> None:
    # Given: a local Wave13 state home for productionization draft scaffolds.
    home = tmp_path / "wave13-state"

    # When: the Wave13 production scenario is built.
    payload = wave13_production_payload(home=home)

    # Then: local records exist while handlers, cron, and network stay closed.
    assert payload["scenario_id"] == "C001"
    assert payload["gateway_draft_created"] is True
    assert payload["api_draft_execution_recorded"] is True
    assert payload["cron_job_planned"] is True
    assert payload["scheduled_objective_job_created"] is True
    assert payload["memory_session_fts_recorded"] is True
    assert payload["skill_candidate_queued"] is True
    assert payload["skill_promoted"] is False
    assert payload["regression_surface_created"] is True
    assert payload["live_transport_allowed"] is False
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False


def test_wave13_blocks_payload_fails_closed_and_redacts_secret(
    tmp_path: Path,
) -> None:
    # Given: a secret-like sample and a local Wave13 state home.
    raw_secret = "sk-wave13-secret"

    # When: the Wave13 block scenario exercises unsafe replay and live paths.
    payload = wave13_blocks_payload(home=tmp_path / "wave13-state", raw_secret=raw_secret)

    # Then: every unsafe path blocks and no raw secret reaches the payload.
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["scenario_id"] == "C002"
    assert payload["gateway_without_lease"] == "blocked"
    assert payload["cron_without_lease"] == "blocked"
    assert payload["duplicate_schedule_idempotent"] is True
    assert payload["conflicting_schedule_replay"] == "blocked"
    assert payload["memory_raw_secret_redacted"] is True
    assert payload["skill_auto_promotion"] == "blocked"
    assert payload["live_transport_enablement"] == "blocked"
    assert payload["unleased_live_transport_opened"] is False
    assert payload["raw_secret_present"] is False
    assert raw_secret not in serialized


def test_record_api_draft_execution_blocks_without_runtime_lease() -> None:
    # Given: an API draft request without runtime authority.
    request = GatewayDraftRequest(
        request_id="wave13.api.no-lease",
        capability_id="api.tool.invoke",
        route="/local/api/wave13",
        method="POST",
        body='{"execute": "draft-record-only"}',
    )

    # When: the API draft execution is recorded without a RuntimeLease.
    result = record_api_draft_execution(
        request=request,
        lease=None,
        now=datetime(2026, 6, 2, tzinfo=timezone.utc),
    )

    # Then: the runtime blocks before recording, handler execution, or network.
    assert result.decision == "blocked"
    assert result.reason == "missing_runtime_lease"
    assert result.record is None
    assert result.handler_executed is False
    assert result.network_opened is False


def test_record_api_draft_execution_blocks_live_network_without_scope() -> None:
    # Given: an API draft request tries to carry live network intent.
    request = GatewayDraftRequest(
        request_id="wave13.api.live-network",
        capability_id="api.tool.invoke",
        route="/local/api/wave13",
        method="POST",
        body='{"execute": "draft-record-only"}',
        live_network=True,
        network_host="gateway.local",
    )

    # When: the API draft is authorized by a non-live Wave13 lease.
    result = record_api_draft_execution(
        request=request,
        lease=_test_wave13_lease(),
        now=datetime(2026, 6, 2, tzinfo=timezone.utc),
    )

    # Then: the runtime blocks instead of storing a live-network draft.
    assert result.decision == "blocked"
    assert result.reason == "live_network_without_scope"
    assert result.record is None
    assert result.network_opened is False


def test_gateway_and_api_records_redact_embedded_secret_spans() -> None:
    # Given: gateway and API draft fields contain embedded token-shaped values.
    lease = _test_wave13_lease()
    secrets = (
        "sk-live-test-fixture",
        "ghp_TEST_FIXTURE",
        "github_pat_TEST_FIXTURE",
        "xoxb-test-fixture",
    )
    joined = " ".join(secrets)
    gateway_request = GatewayDraftRequest(
        request_id="wave13.gateway.secret",
        capability_id="gateway.local.draft",
        route="/local/{0}".format(secrets[0]),
        method="POST",
        body=json.dumps({"credential": secrets[0], "all": joined}, sort_keys=True),
    )
    api_request = GatewayDraftRequest(
        request_id="wave13.api.secret",
        capability_id="api.tool.invoke",
        route="/local/api/{0}".format(secrets[1]),
        method="POST",
        body=json.dumps({"credential": secrets[2], "all": joined}, sort_keys=True),
    )

    # When: draft records are created through the gateway/API surfaces.
    gateway = create_gateway_draft(
        request=gateway_request,
        lease=lease,
        now=datetime(2026, 6, 2, tzinfo=timezone.utc),
    )
    api = record_api_draft_execution(
        request=api_request,
        lease=lease,
        now=datetime(2026, 6, 2, tzinfo=timezone.utc),
    )

    # Then: persisted route/body fields contain redacted spans only.
    assert gateway.record is not None
    assert api.record is not None
    assert gateway.record.route == "/local/sk-...redacted"
    assert '"credential": "sk-...redacted"' in gateway.record.redacted_body
    assert api.record.route == "/local/api/[redacted-secret]"
    assert '"credential": "[redacted-secret]"' in api.record.redacted_body
    persisted = json.dumps(
        {
            "gateway_route": gateway.record.route,
            "gateway_body": gateway.record.redacted_body,
            "api_route": api.record.route,
            "api_body": api.record.redacted_body,
        },
        sort_keys=True,
    )
    for secret in secrets:
        assert secret not in persisted
    assert "sk-...redacted" in persisted
    assert "[redacted-secret]" in persisted


def _test_wave13_lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave13.lease.test",
        objective_id="wave13.objective.production",
        principal_id="wave13.principal.worker",
        run_id="wave13.run.test",
        allowed_capabilities=(
            "gateway.local.draft",
            "api.tool.invoke",
            "cron.schedule.tick",
            "plugin.local.skill_review",
        ),
        credential_scopes=("external.gateway.readonly",),
        network_hosts=("gateway.local",),
        budget_limit=100,
        evidence_target="mneme.wave13.production",
        live_transport_allowed=False,
        issued_at=datetime(2026, 6, 2, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
    )
