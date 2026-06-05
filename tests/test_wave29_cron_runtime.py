from __future__ import annotations

from datetime import datetime, timezone

from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.workflow_runtime import StandingOrderRequest, StandingOrderRuntime


NOW = datetime(2026, 6, 4, 10, 30, tzinfo=timezone.utc)


def test_standing_order_plans_dry_run_only_under_cron_lease() -> None:
    # Given: a standing order only asks for a scheduled objective tick.
    runtime = StandingOrderRuntime()
    request = StandingOrderRequest(
        standing_order_id="standing.daily.status",
        objective="summarize local project status",
        cron_expression="0 9 * * *",
        idempotency_key="standing-daily-status-v1",
        evidence_target="mneme.wave29.cron",
    )

    # When: the request is planned under a matching runtime lease.
    result = runtime.plan(request=request, lease=_cron_lease(), now=NOW)
    replay = runtime.plan(request=request, lease=_cron_lease(), now=NOW)

    # Then: Zeus creates only a dry-run plan with recurrence guard and no side effects.
    assert result.decision == "planned"
    assert result.record is not None
    assert result.record.cron_enabled is False
    assert result.record.recurrence_guard_enabled is True
    assert result.record.live_delivery_allowed is False
    assert result.handler_executed is False
    assert result.network_opened is False
    assert result.live_production_claimed is False
    assert replay.decision == "idempotent_replay"


def test_standing_order_blocks_headless_destructive_live_or_delivery_without_approval() -> None:
    # Given: a headless order tries to gain powers that cron must not grant by itself.
    runtime = StandingOrderRuntime()
    request = StandingOrderRequest(
        standing_order_id="standing.deploy.live",
        objective="deploy and notify a channel",
        cron_expression="*/5 * * * *",
        idempotency_key="standing-deploy-live-v1",
        evidence_target="mneme.wave29.cron",
        destructive_action_requested=True,
        live_delivery_requested=True,
        delivery_targets=("slack://ops",),
    )

    # When: it is evaluated without human approval.
    result = runtime.plan(request=request, lease=_cron_lease(live=False), now=NOW)

    # Then: automation security blocks before handlers, network, or delivery open.
    assert result.decision == "blocked"
    assert result.record is None
    assert "headless_destructive_requires_approval" in result.reasons
    assert "headless_delivery_requires_approval" in result.reasons
    assert result.handler_executed is False
    assert result.network_opened is False


def test_standing_order_blocks_live_delivery_without_live_transport_scope() -> None:
    # Given: an operator approval exists, but the runtime lease is still not live.
    runtime = StandingOrderRuntime()
    request = StandingOrderRequest(
        standing_order_id="standing.ops.notify",
        objective="notify an external channel",
        cron_expression="15 * * * *",
        idempotency_key="standing-ops-notify-v1",
        evidence_target="mneme.wave29.cron",
        live_delivery_requested=True,
        delivery_targets=("webhook://ops",),
        approval_receipt_id="approval.ops.notify.1",
    )

    # When: the standing order is planned with a non-live lease.
    result = runtime.plan(request=request, lease=_cron_lease(live=False), now=NOW)

    # Then: human approval alone does not widen transport authority.
    assert result.decision == "blocked"
    assert "live_delivery_requires_live_transport_scope" in result.reasons
    assert result.network_opened is False


def _cron_lease(*, live: bool = False) -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave29.lease.cron",
        objective_id="wave29.objective.cron",
        principal_id="wave29.principal.operator",
        run_id="wave29.run.cron",
        allowed_capabilities=("cron.schedule.tick",),
        credential_scopes=("external.gateway.readonly",),
        network_hosts=("gateway.local",),
        budget_limit=100,
        evidence_target="mneme.wave29.cron",
        live_transport_allowed=live,
        issued_at=datetime(2026, 6, 4, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 5, tzinfo=timezone.utc),
    )
