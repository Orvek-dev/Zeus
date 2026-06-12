from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from zeus_agent.runtime_lease import RuntimeIntakeRequest, RuntimeKind, RuntimeLease, RuntimeLeaseBuilder
from zeus_agent.security.planning import SecurityPlanBuilder, SecurityPlanningRequest

ISSUED_AT = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
EXPIRES_AT = datetime(2026, 6, 2, 13, 0, tzinfo=timezone.utc)


def _lease(*, live_transport_allowed: bool = False) -> RuntimeLease:
    return RuntimeLease(
        lease_id="g002.lease.live_connection",
        objective_id="g002.objective.live_connection",
        principal_id="g002.principal.worker_a",
        run_id="g002.run.fixture",
        allowed_capabilities=(
            "provider.external.generate",
            "mcp.server.call",
            "web.research.fetch",
            "github.repo.inspect",
            "gateway.dispatch.send",
            "browser.page.inspect",
            "terminal.run",
            "sandbox.remote.execute",
            "plugin.local.execute",
        ),
        credential_scopes=(
            "external.openai.readonly",
            "external.github.readonly",
            "external.gateway.readonly",
        ),
        network_hosts=(
            "api.openai.local",
            "github.local",
            "gateway.local",
        ),
        budget_limit=1_000,
        evidence_target="mneme.g002.live_connection",
        live_transport_allowed=live_transport_allowed,
        issued_at=ISSUED_AT,
        expires_at=EXPIRES_AT,
    )


@pytest.mark.parametrize(
    ("runtime_kind", "capability_id"),
    [
        ("provider", "provider.external.generate"),
        ("mcp", "mcp.server.call"),
        ("web", "web.research.fetch"),
        ("github", "github.repo.inspect"),
        ("gateway", "gateway.dispatch.send"),
        ("browser", "browser.page.inspect"),
        ("terminal", "terminal.run"),
        ("sandbox", "sandbox.remote.execute"),
        ("plugin", "plugin.local.execute"),
    ],
)
def test_live_connection_runtime_surfaces_authorize_without_side_effects(
    runtime_kind: RuntimeKind,
    capability_id: str,
) -> None:
    # Given: a G002 lease that names every live connection surface namespace.
    lease = _lease()
    request = RuntimeIntakeRequest(
        runtime_kind=runtime_kind,
        capability_id=capability_id,
        budget_required=1,
        evidence_target=lease.evidence_target,
    )

    # When: the runtime lease boundary authorizes the request.
    result = RuntimeLeaseBuilder().authorize(lease, request, now=ISSUED_AT)

    # Then: scoped authority is returned without executing handlers or opening networks.
    assert result.decision == "allowed"
    assert result.reason == "runtime_lease_allowed"
    assert result.handler_executed is False
    assert result.network_opened is False
    assert result.authority is not None
    assert [grant.capability_id for grant in result.authority.capability_grants] == [
        capability_id,
    ]


def test_runtime_lease_blocks_missing_expired_and_scope_mismatched_live_surface() -> None:
    # Given: a browser surface request and no valid lease path.
    request = RuntimeIntakeRequest(
        runtime_kind="browser",
        capability_id="browser.page.inspect",
        budget_required=1,
        evidence_target="mneme.g002.live_connection",
    )

    # When: the lease is missing, expired, or mismatched to the capability namespace.
    missing = RuntimeLeaseBuilder().authorize(None, request, now=ISSUED_AT)
    expired = RuntimeLeaseBuilder().authorize(_lease(), request, now=EXPIRES_AT)
    mismatch = RuntimeLeaseBuilder().authorize(
        _lease(),
        RuntimeIntakeRequest(
            runtime_kind="browser",
            capability_id="terminal.run",
            budget_required=1,
            evidence_target="mneme.g002.live_connection",
        ),
        now=ISSUED_AT,
    )

    # Then: every case fails closed before runtime side effects.
    assert missing.reason == "missing_runtime_lease"
    assert expired.reason == "runtime_lease_expired"
    assert mismatch.reason == "runtime_kind_capability_mismatch"
    assert missing.handler_executed is False
    assert expired.handler_executed is False
    assert mismatch.handler_executed is False


def test_runtime_lease_blocks_credential_mismatch_and_redacts_secret_like_scope() -> None:
    # Given: a GitHub surface lease with readonly credential scope only.
    lease = _lease()

    # When: the request widens credentials or passes a secret-like value as scope.
    mismatch = RuntimeLeaseBuilder().authorize(
        lease,
        RuntimeIntakeRequest(
            runtime_kind="github",
            capability_id="github.repo.inspect",
            credential_scope="external.github.admin",
            budget_required=1,
            evidence_target=lease.evidence_target,
        ),
        now=ISSUED_AT,
    )
    raw_secret = "ghp_TEST_FIXTURE"
    redacted = RuntimeLeaseBuilder().authorize(
        lease,
        RuntimeIntakeRequest(
            runtime_kind="github",
            capability_id="github.repo.inspect",
            credential_scope=raw_secret,
            budget_required=1,
            evidence_target=lease.evidence_target,
        ),
        now=ISSUED_AT,
    )

    # Then: both block, and the secret-like fixture is not serialized.
    serialized = redacted.model_dump_json()
    assert mismatch.decision == "blocked"
    assert mismatch.reason == "authority_widening"
    assert redacted.decision == "blocked"
    assert redacted.reason == "unsafe_credential"
    assert redacted.redacted_input == "[redacted-secret]"
    assert raw_secret not in serialized
    assert redacted.handler_executed is False
    assert redacted.network_opened is False


def test_runtime_lease_blocks_live_network_without_authorized_transport_or_host() -> None:
    # Given: a provider request that would need live network authority.
    request = RuntimeIntakeRequest(
        runtime_kind="provider",
        capability_id="provider.external.generate",
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
        live_network=True,
        budget_required=1,
        evidence_target="mneme.g002.live_connection",
    )

    # When: live transport is not enabled or the requested host is outside the lease.
    no_transport = RuntimeLeaseBuilder().authorize(_lease(), request, now=ISSUED_AT)
    bad_host = RuntimeLeaseBuilder().authorize(
        _lease(live_transport_allowed=True),
        RuntimeIntakeRequest(
            runtime_kind="provider",
            capability_id="provider.external.generate",
            credential_scope="external.openai.readonly",
            network_host="unknown.local",
            live_network=True,
            budget_required=1,
            evidence_target="mneme.g002.live_connection",
        ),
        now=ISSUED_AT,
    )

    # Then: both paths block without opening the network.
    assert no_transport.reason == "live_network_without_scope"
    assert bad_host.reason == "live_network_without_scope"
    assert no_transport.network_opened is False
    assert bad_host.network_opened is False


def test_runtime_lease_blocks_evidence_scope_bypass() -> None:
    # Given: a terminal request that tries to write evidence outside the lease target.
    request = RuntimeIntakeRequest(
        runtime_kind="terminal",
        capability_id="terminal.run",
        budget_required=1,
        evidence_target="mneme.g002.other_target",
    )

    # When: authorization compares the request evidence scope to the lease.
    result = RuntimeLeaseBuilder().authorize(_lease(), request, now=ISSUED_AT)

    # Then: evidence scope bypass blocks before terminal execution.
    assert result.decision == "blocked"
    assert result.reason == "evidence_scope_bypass"
    assert result.handler_executed is False


def test_security_planning_blocks_live_connection_surface_bypass_modes() -> None:
    # Given: live connection planning requests across credential, transport, and evidence bypass paths.
    lease = _lease()
    builder = SecurityPlanBuilder()
    raw_secret = "sk-live-secret"

    # When: security planning evaluates unsafe requests.
    missing = builder.build(
        SecurityPlanningRequest(
            surface_kind="browser",
            capability_id="browser.page.inspect",
            dry_run=True,
        ),
    )
    credential = builder.build(
        SecurityPlanningRequest(
            surface_kind="github",
            capability_id="github.repo.inspect",
            requested_scope=f"token={raw_secret}",
            dry_run=True,
        ),
        runtime_lease=lease,
    )
    live_network = builder.build(
        SecurityPlanningRequest(
            surface_kind="provider",
            capability_id="provider.external.generate",
            requested_scope="external.openai.readonly",
            network_host="api.openai.local",
            dry_run=False,
            evidence_target=lease.evidence_target,
        ),
        runtime_lease=lease,
    )
    evidence_bypass = builder.build(
        SecurityPlanningRequest(
            surface_kind="gateway",
            capability_id="gateway.dispatch.send",
            requested_scope="external.gateway.readonly",
            network_host="gateway.local",
            dry_run=True,
            evidence_target="mneme.g002.other_target",
        ),
        runtime_lease=lease,
    )

    # Then: planning blocks without handler, network, or raw secret echo.
    serialized = json.dumps(credential.model_dump(mode="json"), sort_keys=True)
    assert missing.reason == "missing_runtime_lease"
    assert credential.reason == "unsafe_credential_scope"
    assert credential.redacted_input == "[redacted-secret]"
    assert raw_secret not in serialized
    assert live_network.reason == "live_transport_not_authorized"
    assert evidence_bypass.reason == "evidence_scope_bypass"
    assert missing.handler_executed is False
    assert credential.handler_executed is False
    assert live_network.network_opened is False
    assert evidence_bypass.network_opened is False
