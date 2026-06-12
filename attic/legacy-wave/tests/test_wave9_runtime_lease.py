from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from zeus_agent.runtime_lease import (
    RuntimeIntakeRequest,
    RuntimeLease,
    RuntimeLeaseBuilder,
    wave9_fixture_lease,
)
from zeus_agent.wave9_scenarios import (
    wave9_runtime_blocks_payload,
    wave9_runtime_lease_payload,
)


def test_runtime_lease_creates_authority_context_with_scoped_grants() -> None:
    # Given: a deterministic Wave9 lease with provider authority.
    lease = wave9_fixture_lease()
    request = RuntimeIntakeRequest(
        runtime_kind="provider",
        capability_id="provider.external.generate",
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
        budget_required=25,
        evidence_target=lease.evidence_target,
    )

    # When: runtime intake validates the lease before handler preparation.
    result = RuntimeLeaseBuilder().authorize(lease, request, now=lease.issued_at)

    # Then: scoped authority exists and no provider handler or network side effect ran.
    assert result.decision == "allowed"
    assert result.reason == "runtime_lease_allowed"
    assert result.authority is not None
    assert result.authority.principal_id == lease.principal_id
    assert result.authority.goal_contract_id == lease.objective_id
    assert [grant.capability_id for grant in result.authority.capability_grants] == [
        "provider.external.generate",
    ]
    assert {grant.capability_id for grant in result.authority.capability_grants}.isdisjoint(
        {"mcp.echo", "gateway.webhook.dispatch", "cron.schedule.tick", "api.tool.invoke", "plugin.local.execute"},
    )
    assert result.authority.network_grants == []
    assert [
        (grant.capability_id, grant.credential_scope)
        for grant in result.authority.credential_grants
    ] == [("provider.external.generate", "external.openai.readonly")]
    assert result.credential_scope_label == "external.openai.readonly"
    assert result.budget_limit == lease.budget_limit
    assert result.evidence_target == lease.evidence_target
    assert result.handler_executed is False
    assert result.network_opened is False
    assert result.no_secret_echo is True


def test_authorize_rejects_expired_lease_before_provider_side_effects() -> None:
    # Given: a deterministic Wave9 lease that is past its expiry at authorization time.
    lease = wave9_fixture_lease()
    request = RuntimeIntakeRequest(
        runtime_kind="provider",
        capability_id="provider.external.generate",
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
        budget_required=25,
        evidence_target=lease.evidence_target,
    )
    after_expiry = datetime(2026, 6, 3, 0, 0, 1, tzinfo=timezone.utc)

    # When: runtime intake validates the lease before provider preparation.
    result = RuntimeLeaseBuilder().authorize(lease, request, now=after_expiry)

    # Then: the expired lease fails closed without authority, handler, or network side effects.
    assert result.decision == "blocked"
    assert result.reason == "runtime_lease_expired"
    assert result.authority is None
    assert result.handler_executed is False
    assert result.network_opened is False


@pytest.mark.parametrize(
    ("intake_request", "expected_reason"),
    [
        (
            RuntimeIntakeRequest(
                runtime_kind="provider",
                capability_id="provider.external.admin",
                budget_required=1,
                evidence_target="mneme.wave9.runtime_lease",
            ),
            "authority_widening",
        ),
        (
            RuntimeIntakeRequest(
                runtime_kind="provider",
                capability_id="provider.external.generate",
                requested_capabilities=("provider.external.admin",),
                budget_required=1,
                evidence_target="mneme.wave9.runtime_lease",
            ),
            "scope_escalation",
        ),
        (
            RuntimeIntakeRequest(
                runtime_kind="provider",
                capability_id="provider.external.generate",
                credential_scope="sk-live-secret",
                budget_required=1,
                evidence_target="mneme.wave9.runtime_lease",
            ),
            "unsafe_credential",
        ),
        (
            RuntimeIntakeRequest(
                runtime_kind="provider",
                capability_id="provider.external.generate",
                network_host="api.openai.local",
                live_network=True,
                budget_required=1,
                evidence_target="mneme.wave9.runtime_lease",
            ),
            "live_network_without_scope",
        ),
        (
            RuntimeIntakeRequest(
                runtime_kind="provider",
                capability_id="provider.external.generate",
                network_host="api.unknown.local",
                live_network=True,
                budget_required=1,
                evidence_target="mneme.wave9.runtime_lease",
            ),
            "live_network_without_scope",
        ),
        (
            RuntimeIntakeRequest(
                runtime_kind="provider",
                capability_id="provider.external.generate",
                budget_required=10_001,
                evidence_target="mneme.wave9.runtime_lease",
            ),
            "over_budget",
        ),
        (
            RuntimeIntakeRequest(
                runtime_kind="provider",
                capability_id="provider.external.generate",
                budget_required=1,
                evidence_target="mneme.wave9.other_target",
            ),
            "evidence_scope_bypass",
        ),
    ],
)
def test_runtime_lease_blocks_unsafe_runtime_intake_before_handlers(
    intake_request: RuntimeIntakeRequest,
    expected_reason: str,
) -> None:
    # Given: a deterministic Wave9 lease and an unsafe intake request.
    lease = wave9_fixture_lease()

    # When: runtime intake runs before provider or connector preparation.
    result = RuntimeLeaseBuilder().authorize(lease, intake_request, now=lease.issued_at)

    # Then: unsafe intake fails closed without handler or network side effects.
    assert result.decision == "blocked"
    assert result.reason == expected_reason
    assert result.authority is None
    assert result.handler_executed is False
    assert result.network_opened is False
    assert result.no_secret_echo is True
    assert "sk-live-secret" not in result.model_dump_json()


def test_runtime_kind_capability_mismatch_blocks_confused_deputy() -> None:
    # Given: a lease that allows MCP, but a request labels MCP authority as provider runtime.
    lease = wave9_fixture_lease()
    request = RuntimeIntakeRequest(
        runtime_kind="provider",
        capability_id="mcp.echo",
        budget_required=1,
        evidence_target=lease.evidence_target,
    )

    # When: authorization validates runtime kind against the requested capability namespace.
    result = RuntimeLeaseBuilder().authorize(lease, request, now=lease.issued_at)

    # Then: the confused-deputy request blocks before any authority is returned.
    assert result.decision == "blocked"
    assert result.reason == "runtime_kind_capability_mismatch"
    assert result.authority is None


def test_runtime_lease_blocks_missing_and_malformed_lease() -> None:
    # Given: a provider request and no usable lease context.
    request = RuntimeIntakeRequest(
        runtime_kind="provider",
        capability_id="provider.external.generate",
        budget_required=1,
        evidence_target="mneme.wave9.runtime_lease",
    )

    # When: runtime intake receives no lease.
    result = RuntimeLeaseBuilder().authorize(None, request)

    # Then: the request is blocked before any runtime handler can execute.
    assert result.decision == "blocked"
    assert result.reason == "missing_runtime_lease"
    assert result.handler_executed is False
    assert result.network_opened is False

    # When: runtime intake receives an arbitrary non-RuntimeLease object.
    malformed_result = RuntimeLeaseBuilder().authorize(object(), request)

    # Then: malformed lease objects fail closed without trusting arbitrary attributes.
    assert malformed_result.decision == "blocked"
    assert malformed_result.reason == "malformed_runtime_lease"
    assert malformed_result.authority is None

    # Given: malformed principal/objective ids at the lease boundary.
    fixture = wave9_fixture_lease()
    raw = fixture.model_dump(mode="json")
    raw["principal_id"] = "bad principal"
    raw["objective_id"] = " "

    # When / Then: malformed ids cannot cross the RuntimeLease boundary.
    with pytest.raises(ValidationError):
        RuntimeLease.model_validate(raw)


def test_wave9_happy_and_block_scenarios_are_json_safe() -> None:
    # Given: the Wave9 deterministic scenarios.
    raw_secret = "ghp_TEST_FIXTURE"

    # When: happy and block payloads are rendered.
    happy = wave9_runtime_lease_payload()
    blocked = wave9_runtime_blocks_payload(raw_secret=raw_secret)

    # Then: happy scope is allowed while block labels fail closed without secrets.
    assert happy["runtime_lease_validated"] is True
    assert happy["principal_id"] == "wave9.principal.worker_a"
    assert happy["objective_id"] == "wave9.objective.runtime_lease"
    assert happy["provider_scope"] == "allowed"
    assert happy["mcp_scope"] == "allowed"
    assert happy["gateway_scope"] == "allowed"
    assert happy["cron_scope"] == "allowed"
    assert happy["api_tool_scope"] == "allowed"
    assert happy["plugin_scope"] == "allowed"
    assert happy["request_scoped_authority"] is True
    assert happy["provider_authority_capability_grants"] == ["provider.external.generate"]
    assert happy["provider_authority_credential_grants"] == [
        "provider.external.generate:external.openai.readonly",
    ]
    assert happy["provider_authority_network_grants"] == 0
    assert happy["credential_scope_label"] == "external.openai.readonly"
    assert happy["live_transport_allowed"] is False
    assert happy["handler_executed"] is False
    assert happy["network_opened"] is False
    assert happy["no_secret_echo"] is True

    for key in [
        "missing_runtime_lease",
        "malformed_principal",
        "malformed_runtime_lease",
        "runtime_kind_capability_mismatch",
        "authority_widening",
        "scope_escalation",
        "evidence_scope_bypass",
        "unsafe_credential",
        "live_network_without_scope",
        "expired_runtime_lease",
        "over_budget",
    ]:
        assert blocked[key] == "blocked"
    assert blocked["handler_executed"] is False
    assert blocked["network_opened"] is False
    assert blocked["no_secret_echo"] is True
    assert raw_secret not in json.dumps(blocked, sort_keys=True)
