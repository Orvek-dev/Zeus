from __future__ import annotations

import json

from zeus_agent.runtime_lease import wave9_fixture_lease
from zeus_agent.security.planning import SecurityPlanBuilder, SecurityPlanningRequest


def test_security_plan_blocks_live_surfaces_without_runtime_lease() -> None:
    request = SecurityPlanningRequest(
        surface_kind="provider",
        capability_id="provider.external.generate",
    )
    result = SecurityPlanBuilder().build(request)
    assert result.decision == "blocked"
    assert result.reason == "missing_runtime_lease"
    assert result.handler_executed is False
    assert result.network_opened is False


def test_security_plan_allows_dry_run_local_planning_without_lease() -> None:
    request = SecurityPlanningRequest(
        surface_kind="local",
        capability_id="local.workflow.simulate",
        dry_run=True,
    )
    result = SecurityPlanBuilder().build(request)
    assert result.decision == "allowed"
    assert result.reason == "dry_run"
    assert result.handler_executed is False
    assert result.network_opened is False
    assert result.no_secret_echo is True


def test_live_provider_secret_input_is_redacted_and_blocked() -> None:
    request = SecurityPlanningRequest(
        surface_kind="provider",
        capability_id="provider.external.generate",
        requested_scope="provider.credential_scope=sk-live-secret",
        dry_run=True,
    )
    lease = wave9_fixture_lease()

    result = SecurityPlanBuilder().build(request, runtime_lease=lease)
    serialized = json.dumps(result.model_dump(mode="json"), sort_keys=True)

    assert result.decision == "blocked"
    assert result.reason == "unsafe_credential_scope"
    assert result.redacted_input == "provider.credential_scope=sk-...redacted"
    assert "sk-live-secret" not in serialized
    assert result.handler_executed is False
    assert result.network_opened is False


def test_security_plan_blocks_credential_scope_mismatch_even_when_live_enabled() -> None:
    lease = wave9_fixture_lease().model_copy(update={"live_transport_allowed": True})
    result = SecurityPlanBuilder().build(
        SecurityPlanningRequest(
            surface_kind="provider",
            capability_id="provider.external.generate",
            requested_scope="external.openai.admin",
        ),
        runtime_lease=lease,
    )

    assert result.decision == "blocked"
    assert result.reason == "scope_mismatch"
    assert result.scope_matched is False


def test_security_plan_blocks_surface_capability_mismatch_for_safe_surface() -> None:
    result = SecurityPlanBuilder().build(
        SecurityPlanningRequest(
            surface_kind="local",
            capability_id="provider.external.generate",
            dry_run=True,
        ),
    )

    assert result.decision == "blocked"
    assert result.reason == "scope_mismatch"
    assert result.scope_matched is False
    assert result.handler_executed is False
    assert result.network_opened is False


def test_security_plan_blocks_surface_capability_mismatch_with_lease() -> None:
    lease = wave9_fixture_lease()
    result = SecurityPlanBuilder().build(
        SecurityPlanningRequest(
            surface_kind="provider",
            capability_id="mcp.echo",
            requested_scope="external.openai.readonly",
            dry_run=True,
        ),
        runtime_lease=lease,
    )

    assert result.decision == "blocked"
    assert result.reason == "scope_mismatch"
    assert result.scope_matched is False


def test_live_capable_surface_with_fixture_lease() -> None:
    lease = wave9_fixture_lease()
    builder = SecurityPlanBuilder()

    blocked = builder.build(
        SecurityPlanningRequest(
            surface_kind="provider",
            capability_id="provider.external.generate",
            requested_scope="external.openai.readonly",
            dry_run=False,
        ),
        runtime_lease=lease,
    )
    dry_run_allowed = builder.build(
        SecurityPlanningRequest(
            surface_kind="provider",
            capability_id="provider.external.generate",
            requested_scope="external.openai.readonly",
            dry_run=True,
        ),
        runtime_lease=lease,
    )
    widened = builder.build(
        SecurityPlanningRequest(
            surface_kind="provider",
            capability_id="provider.external.admin",
            requested_scope="external.openai.admin",
            dry_run=True,
        ),
        runtime_lease=lease,
    )

    assert blocked.decision == "blocked"
    assert blocked.reason == "live_transport_not_authorized"
    assert dry_run_allowed.decision == "allowed"
    assert dry_run_allowed.reason == "dry_run"
    assert widened.decision == "blocked"
    assert widened.reason == "scope_mismatch"
