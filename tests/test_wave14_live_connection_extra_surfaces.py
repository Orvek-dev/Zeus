from __future__ import annotations

from datetime import datetime, timezone

from zeus_agent.live_connection_runtime import LiveConnectionRequest, LiveConnectionRouter
from zeus_agent.runtime_lease import RuntimeLease


def test_router_plans_github_browser_and_terminal_surfaces_under_lease() -> None:
    lease = RuntimeLease(
        lease_id="wave14.lease.extra_surfaces",
        objective_id="wave14.objective.live_connection",
        principal_id="wave14.principal.worker_a2",
        run_id="wave14.run.extra",
        allowed_capabilities=(
            "github.repo.inspect",
            "browser.page.inspect",
            "terminal.run",
        ),
        credential_scopes=("external.github.readonly",),
        network_hosts=("github.local", "browser.local"),
        budget_limit=10_000,
        evidence_target="mneme.wave14.live_connection",
        live_transport_allowed=False,
        issued_at=datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc),
    )
    requests = (
        LiveConnectionRequest(
            request_id="wave14.req.github",
            surface_kind="github",
            capability_id="github.repo.inspect",
            credential_scope="external.github.readonly",
            network_host="github.local",
        ),
        LiveConnectionRequest(
            request_id="wave14.req.browser",
            surface_kind="browser",
            capability_id="browser.page.inspect",
            network_host="browser.local",
        ),
        LiveConnectionRequest(
            request_id="wave14.req.terminal",
            surface_kind="terminal",
            capability_id="terminal.run",
            sandbox_command="pwd",
        ),
    )

    plan = LiveConnectionRouter().plan(
        requests,
        runtime_lease=lease,
        now=datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc),
    )

    assert plan.decision == "planned"
    assert plan.planned_surface_kinds == ("github", "browser", "terminal")
    assert plan.handler_executed is False
    assert plan.network_opened is False
    assert plan.no_secret_echo is True
