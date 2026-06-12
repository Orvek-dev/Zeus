from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from zeus_agent.kernel.authority import (
    ApprovalReceipt,
    AuthorityContext,
    CapabilityGrant,
    CredentialGrant,
    NetworkGrant,
)
from zeus_agent.runtime_promotion import (
    LiveTransportPromotionGuard,
    LiveTransportPromotionRequest,
    RollbackPlan,
)
from zeus_agent.wave6_scenarios import wave6_promotion_controls_payload
from zeus_agent.workflow_runtime.jobs import RetryPolicy


def test_wave6_blocks_live_transport_without_approval_before_side_effects(
    tmp_path: Path,
) -> None:
    # Given: a live provider/API transport promotion is requested without approval.
    # When: Wave6 evaluates the promotion controls and persists the attempt.
    payload = wave6_promotion_controls_payload(tmp_path)

    # Then: live transport is blocked before handler or network execution.
    assert payload["fake_local_only"] is True
    assert payload["no_external_side_effects"] is True
    assert payload["no_secret_echo"] is True
    assert payload["promotion"]["decision"] == "blocked"
    assert payload["promotion"]["reason"] == "live_transport_not_authorized"
    assert payload["promotion"]["approval_required"] is True
    assert payload["promotion"]["handler_executed"] is False
    assert payload["promotion"]["network_opened"] is False
    assert payload["promotion"]["retry_policy"] == {
        "max_attempts": 3,
        "backoff_seconds": 5,
    }
    assert payload["promotion"]["rollback_plan"] == {
        "command": "disable-live-transport",
        "target": "provider.external.generate",
        "executed": False,
    }
    assert payload["runtime_counts"]["promotion_attempts"] == 1

    state_db = Path(str(payload["state_db"]))
    with sqlite3.connect(state_db) as connection:
        rows = connection.execute(
            """
            SELECT promotion_id, capability_id, decision, reason, approval_required,
                   handler_executed, network_opened, idempotency_key
            FROM runtime_state_transport_promotions
            """
        ).fetchall()

    assert rows == [
        (
            "promotion-wave6-001",
            "provider.external.generate",
            "blocked",
            "live_transport_not_authorized",
            1,
            0,
            0,
            "idem-wave6-promotion-001",
        )
    ]


def test_wave6_promotion_guard_rejects_secret_like_transport_scope() -> None:
    # Given: a caller sends raw secret material as a live transport scope.
    raw_secret = "ghp_TEST_FIXTURE"
    guard = LiveTransportPromotionGuard()
    request = LiveTransportPromotionRequest(
        promotion_id="promotion-secret",
        capability_id="api.fetch",
        transport_kind="api",
        idempotency_key="idem-secret",
        credential_scope=raw_secret,
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=1),
        rollback_plan=RollbackPlan(command="disable-api", target="api.fetch"),
    )

    # When: the promotion guard evaluates the request.
    result = guard.evaluate(request)

    # Then: it blocks without echoing the raw secret.
    serialized = json.dumps(result.model_dump(mode="json"), sort_keys=True)
    assert result.decision == "blocked"
    assert result.reason == "secret_like_credential_scope"
    assert result.handler_executed is False
    assert result.network_opened is False
    assert raw_secret not in serialized


def test_wave6_promotion_guard_requires_requested_capability_approval() -> None:
    # Given: live transport is enabled and authority grants the requested provider scope.
    guard = LiveTransportPromotionGuard(live_transport_enabled=True)
    request = LiveTransportPromotionRequest(
        promotion_id="promotion-live",
        capability_id="provider.external.generate",
        transport_kind="provider",
        idempotency_key="idem-live",
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=1),
        rollback_plan=RollbackPlan(
            command="disable-live-transport",
            target="provider.external.generate",
        ),
    )
    authority = AuthorityContext(
        principal_id="principal-live",
        run_id="run-live",
        goal_contract_id="goal-live",
        capability_grants=[CapabilityGrant(capability_id="provider.external.generate")],
        network_grants=[
            NetworkGrant(
                capability_id="provider.external.generate",
                network_host="api.openai.local",
            )
        ],
        credential_grants=[
            CredentialGrant(
                capability_id="provider.external.generate",
                credential_scope="external.openai.readonly",
            )
        ],
    )
    approval = ApprovalReceipt(
        principal_id="principal-live",
        run_id="run-live",
        goal_contract_id="goal-live",
        approved_capabilities=[],
    )

    # When: the approval receipt does not explicitly approve the requested capability.
    result = guard.evaluate(
        request,
        authority=authority,
        approval_receipt=approval,
    )

    # Then: the guard still blocks before handler or network execution.
    assert result.decision == "blocked"
    assert result.reason == "approval_missing_capability"
    assert result.approval_required is True
    assert result.handler_executed is False
    assert result.network_opened is False


def test_wave6_promotion_guard_rejects_unrelated_approved_capability() -> None:
    # Given: live transport is enabled with authority for the requested provider scope.
    guard = LiveTransportPromotionGuard(live_transport_enabled=True)
    request = _live_provider_request("promotion-unrelated")
    authority = _live_provider_authority()
    approval = ApprovalReceipt(
        principal_id="principal-live",
        run_id="run-live",
        goal_contract_id="goal-live",
        approved_capabilities=["mcp.echo"],
    )

    # When: the approval receipt names a different capability.
    result = guard.evaluate(request, authority=authority, approval_receipt=approval)

    # Then: the promotion remains blocked before handler or network execution.
    assert result.decision == "blocked"
    assert result.reason == "approval_missing_capability"
    assert result.handler_executed is False
    assert result.network_opened is False


def test_wave6_promotion_guard_allows_only_requested_approval_with_scope() -> None:
    # Given: live transport is enabled with matching approval and authority scope.
    guard = LiveTransportPromotionGuard(live_transport_enabled=True)
    request = _live_provider_request("promotion-allowed")
    authority = _live_provider_authority()
    approval = _approval(["provider.external.generate"])

    # When: all explicit future-live gates are satisfied.
    result = guard.evaluate(request, authority=authority, approval_receipt=approval)

    # Then: the dry guard can return allowed without executing handler or network work.
    assert result.decision == "allowed"
    assert result.reason == "live_transport_authorized"
    assert result.approval_required is False
    assert result.handler_executed is False
    assert result.network_opened is False


def test_wave6_promotion_guard_blocks_approved_capability_without_scope() -> None:
    # Given: live transport is enabled and the requested capability is approved.
    guard = LiveTransportPromotionGuard(live_transport_enabled=True)
    request = _live_provider_request("promotion-scope-missing")
    authority = AuthorityContext(
        principal_id="principal-live",
        run_id="run-live",
        goal_contract_id="goal-live",
        capability_grants=[CapabilityGrant(capability_id="provider.external.generate")],
    )
    approval = _approval(["provider.external.generate"])

    # When: AuthorityContext lacks required network and credential scope grants.
    result = guard.evaluate(request, authority=authority, approval_receipt=approval)

    # Then: authority still blocks before handler or network execution.
    assert result.decision == "blocked"
    assert result.reason == "network_scope_missing"
    assert result.handler_executed is False
    assert result.network_opened is False


def _live_provider_request(promotion_id: str) -> LiveTransportPromotionRequest:
    return LiveTransportPromotionRequest(
        promotion_id=promotion_id,
        capability_id="provider.external.generate",
        transport_kind="provider",
        idempotency_key="idem-" + promotion_id,
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=1),
        rollback_plan=RollbackPlan(
            command="disable-live-transport",
            target="provider.external.generate",
        ),
    )


def _live_provider_authority() -> AuthorityContext:
    return AuthorityContext(
        principal_id="principal-live",
        run_id="run-live",
        goal_contract_id="goal-live",
        capability_grants=[CapabilityGrant(capability_id="provider.external.generate")],
        network_grants=[
            NetworkGrant(
                capability_id="provider.external.generate",
                network_host="api.openai.local",
            )
        ],
        credential_grants=[
            CredentialGrant(
                capability_id="provider.external.generate",
                credential_scope="external.openai.readonly",
            )
        ],
    )


def _approval(approved_capabilities: list[str]) -> ApprovalReceipt:
    return ApprovalReceipt(
        principal_id="principal-live",
        run_id="run-live",
        goal_contract_id="goal-live",
        approved_capabilities=approved_capabilities,
    )
