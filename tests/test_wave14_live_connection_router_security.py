from __future__ import annotations

from datetime import datetime, timezone

from zeus_agent.live_connection_runtime import (
    LiveConnectionRequest,
    LiveConnectionRouter,
)
from zeus_agent.runtime_lease import RuntimeLease


def _wave14_lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave14.lease.router_security",
        objective_id="wave14.objective.live_connection",
        principal_id="wave14.principal.router_security",
        run_id="wave14.run.router_security",
        allowed_capabilities=("provider.external.plan",),
        credential_scopes=("external.openai.readonly",),
        network_hosts=("api.openai.local",),
        budget_limit=10_000,
        evidence_target="mneme.wave14.live_connection",
        live_transport_allowed=False,
        issued_at=datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc),
    )


def test_router_blocks_expired_lease_and_evidence_scope_bypass() -> None:
    expired_lease = _wave14_lease().model_copy(
        update={
            "issued_at": datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc),
            "expires_at": datetime(2026, 6, 2, 0, 0, tzinfo=timezone.utc),
        },
    )
    request = LiveConnectionRequest(
        request_id="wave14.req.expired",
        surface_kind="provider",
        capability_id="provider.external.plan",
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
    )
    bypass = LiveConnectionRequest(
        request_id="wave14.req.evidence_bypass",
        surface_kind="provider",
        capability_id="provider.external.plan",
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
        evidence_target="mneme.wave14.other_target",
    )

    expired_plan = LiveConnectionRouter().plan(
        (request,),
        runtime_lease=expired_lease,
        now=datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc),
    )
    bypass_plan = LiveConnectionRouter().plan(
        (bypass,),
        runtime_lease=_wave14_lease(),
        now=datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc),
    )

    assert expired_plan.decision == "blocked"
    assert expired_plan.blocked_reasons == ("runtime_lease_expired",)
    assert bypass_plan.decision == "blocked"
    assert bypass_plan.blocked_reasons == ("evidence_scope_bypass",)
    assert expired_plan.handler_executed is False
    assert expired_plan.network_opened is False
    assert bypass_plan.handler_executed is False
    assert bypass_plan.network_opened is False


def test_router_redacts_secret_like_request_id_before_serialization() -> None:
    raw_secret = "sk-audit-route-secret"
    request = LiveConnectionRequest(
        request_id=raw_secret,
        surface_kind="provider",
        capability_id="provider.external.plan",
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
    )

    plan = LiveConnectionRouter().plan(
        (request,),
        runtime_lease=_wave14_lease(),
        now=datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc),
    )
    serialized = plan.model_dump_json()

    assert plan.decision == "planned"
    assert request.request_id == "redacted"
    assert plan.routes[0].request_id == "redacted"
    assert plan.no_secret_echo is True
    assert raw_secret not in request.model_dump_json()
    assert raw_secret not in serialized


def test_router_redacts_private_key_shaped_request_ids_before_serialization() -> None:
    raw_private_key = "private_key=abc123"
    raw_spaced_private_key = "private key:abc123"
    raw_pem = "-----BEGIN PRIVATE KEY-----abc123-----END PRIVATE KEY-----"
    requests = tuple(
        LiveConnectionRequest(
            request_id=raw_secret,
            surface_kind="provider",
            capability_id="provider.external.plan",
            credential_scope="external.openai.readonly",
            network_host="api.openai.local",
        )
        for raw_secret in (raw_private_key, raw_spaced_private_key, raw_pem)
    )

    plan = LiveConnectionRouter().plan(
        requests,
        runtime_lease=_wave14_lease(),
        now=datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc),
    )
    serialized = plan.model_dump_json()

    assert plan.decision == "planned"
    assert plan.no_secret_echo is True
    assert all(route.request_id == "redacted" for route in plan.routes)
    assert raw_private_key not in serialized
    assert raw_spaced_private_key not in serialized
    assert raw_pem not in serialized


def test_router_expiry_uses_injected_clock_for_deterministic_fixtures() -> None:
    request = LiveConnectionRequest(
        request_id="wave14.req.clock",
        surface_kind="provider",
        capability_id="provider.external.plan",
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
    )
    lease = _wave14_lease()

    planned = LiveConnectionRouter().plan(
        (request,),
        runtime_lease=lease,
        now=datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc),
    )
    expired = LiveConnectionRouter().plan(
        (request,),
        runtime_lease=lease,
        now=datetime(2026, 6, 4, 0, 0, 1, tzinfo=timezone.utc),
    )

    assert planned.decision == "planned"
    assert expired.decision == "blocked"
    assert expired.blocked_reasons == ("runtime_lease_expired",)


def test_router_blocks_surface_capability_namespace_mismatch() -> None:
    provider_with_mcp = LiveConnectionRequest(
        request_id="wave14.req.provider_mcp",
        surface_kind="provider",
        capability_id="mcp.server.plan",
    )
    mcp_with_provider = LiveConnectionRequest(
        request_id="wave14.req.mcp_provider",
        surface_kind="mcp",
        capability_id="provider.external.plan",
        mcp_description="trusted plan-only MCP descriptor",
    )
    lease = RuntimeLease(
        lease_id="wave14.lease.namespace_mismatch",
        objective_id="wave14.objective.live_connection",
        principal_id="wave14.principal.router_security",
        run_id="wave14.run.namespace_mismatch",
        allowed_capabilities=("mcp.server.plan", "provider.external.plan"),
        budget_limit=10_000,
        evidence_target="mneme.wave14.live_connection",
        issued_at=datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc),
    )

    plan = LiveConnectionRouter().plan(
        (provider_with_mcp, mcp_with_provider),
        runtime_lease=lease,
        now=datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc),
    )

    assert plan.decision == "blocked"
    assert plan.blocked_reasons == ("runtime_kind_capability_mismatch",)
    assert all(route.decision == "blocked" for route in plan.routes)
    assert plan.handler_executed is False
    assert plan.network_opened is False
