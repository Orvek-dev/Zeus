from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Optional, Sequence

from zeus_agent.capability_runtime import SandboxPolicy
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.security.credentials import redact_secret_spans

from .models import LiveConnectionPlan, LiveConnectionRequest, RoutePlan, SurfaceKind

_PROMPT_INJECTION_MARKERS: Final = (
    "ignore previous",
    "ignore all previous",
    "disregard previous",
    "reveal secrets",
    "system prompt",
)
_SECRET_MARKERS: Final = (
    "sk-",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "api_key",
    "api-key",
    "private_key",
    "private-key",
    "private key",
    "token=",
    "password=",
    "secret=",
    "-----begin",
)
_SURFACE_CAPABILITY_PREFIX: Final[dict[SurfaceKind, str]] = {
    "provider": "provider.",
    "mcp": "mcp.",
    "web": "web.",
    "github": "github.",
    "gateway": "gateway.",
    "browser": "browser.",
    "terminal": "terminal.",
    "sandbox": "sandbox.",
    "plugin": "plugin.",
}
_SURFACE_REASON_BUILDERS: Final[dict[SurfaceKind, Callable[[LiveConnectionRequest], tuple[str, ...]]]] = {
    "provider": lambda request: (),
    "mcp": lambda request: _mcp_reasons(request),
    "web": lambda request: ("web_source_unpinned",) if not request.source_pinned else (),
    "github": lambda request: (
        ("github_source_unpinned",) if not request.source_pinned else ()
    ),
    "gateway": lambda request: (
        ("gateway_target_blocked",) if not request.gateway_target_allowed else ()
    ),
    "browser": lambda request: (),
    "terminal": lambda request: _sandbox_reasons(request),
    "sandbox": lambda request: _sandbox_reasons(request),
    "plugin": lambda request: ("plugin_quarantined",) if request.plugin_quarantined else (),
}


class LiveConnectionRouter:
    def plan(
        self,
        requests: Sequence[LiveConnectionRequest],
        runtime_lease: RuntimeLease | None = None,
        objective_contract_bound: bool = True,
        now: Optional[datetime] = None,
    ) -> LiveConnectionPlan:
        if not objective_contract_bound:
            return LiveConnectionPlan(
                decision="blocked",
                routes=(),
                audit_record_created=True,
                handler_executed=False,
                network_opened=False,
                no_secret_echo=True,
                blocked_reasons=("objective_contract_unbound",),
            )

        routes = tuple(
            self._route_request(request, runtime_lease, now=now)
            for request in requests
        )
        blocked_reasons = _blocked_reasons(routes)
        return LiveConnectionPlan(
            decision="blocked" if blocked_reasons else "planned",
            routes=routes,
            audit_record_created=True,
            handler_executed=False,
            network_opened=False,
            no_secret_echo=_routes_have_no_secret_echo(routes),
            blocked_reasons=blocked_reasons,
        )

    def _route_request(
        self,
        request: LiveConnectionRequest,
        runtime_lease: RuntimeLease | None,
        *,
        now: Optional[datetime],
    ) -> RoutePlan:
        reasons = (
            *_lease_reasons(request, runtime_lease, now=now),
            *_surface_reasons(request),
        )
        if reasons:
            return RoutePlan(
                request_id=request.request_id,
                surface_kind=request.surface_kind,
                decision="blocked",
                reason=";".join(reasons),
                dry_run=request.dry_run,
            )
        return RoutePlan(
            request_id=request.request_id,
            surface_kind=request.surface_kind,
            decision="planned",
            reason="plan_only",
            dry_run=request.dry_run,
        )


def _lease_reasons(
    request: LiveConnectionRequest,
    runtime_lease: RuntimeLease | None,
    *,
    now: Optional[datetime],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if runtime_lease is None:
        if _requires_runtime_lease(request):
            reasons.append("missing_lease")
        return tuple(reasons)

    current_time = _to_utc(now) if now is not None else datetime.now(timezone.utc)
    if runtime_lease.expires_at <= current_time:
        reasons.append("runtime_lease_expired")
    if request.evidence_target != runtime_lease.evidence_target:
        reasons.append("evidence_scope_bypass")
    if not request.capability_id.startswith(_SURFACE_CAPABILITY_PREFIX[request.surface_kind]):
        reasons.append("runtime_kind_capability_mismatch")
    if request.capability_id not in runtime_lease.allowed_capabilities:
        reasons.append("capability_not_allowed")
    if request.credential_scope is not None:
        if request.credential_scope not in runtime_lease.credential_scopes:
            reasons.append("credential_scope_mismatch")
    if request.network_host is not None:
        if request.network_host not in runtime_lease.network_hosts:
            reasons.append("network_host_mismatch")
    if not request.dry_run:
        if request.approval_receipt_id is None:
            reasons.append("missing_approval")
        if not runtime_lease.live_transport_allowed:
            reasons.append("live_transport_disallowed")
    return tuple(reasons)


def _surface_reasons(request: LiveConnectionRequest) -> tuple[str, ...]:
    builder = _SURFACE_REASON_BUILDERS[request.surface_kind]
    return builder(request)


def _mcp_reasons(request: LiveConnectionRequest) -> tuple[str, ...]:
    description = (request.mcp_description or "").lower()
    if any(marker in description for marker in _PROMPT_INJECTION_MARKERS):
        return ("mcp_prompt_injection",)
    return ()


def _sandbox_reasons(request: LiveConnectionRequest) -> tuple[str, ...]:
    if request.sandbox_command is None:
        return ()
    decision = SandboxPolicy().decide_command(request.sandbox_command, Path("."))
    if decision.decision == "allowed":
        return ()
    if decision.reason == "network_command_blocked":
        return ("sandbox_network_command_blocked",)
    return ("sandbox_command_blocked",)


def _requires_runtime_lease(request: LiveConnectionRequest) -> bool:
    return True


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _blocked_reasons(routes: tuple[RoutePlan, ...]) -> tuple[str, ...]:
    reasons: list[str] = []
    for route in routes:
        if route.decision == "blocked":
            for reason in route.reason.split(";"):
                if reason not in reasons:
                    reasons.append(reason)
    return tuple(reasons)


def _routes_have_no_secret_echo(routes: tuple[RoutePlan, ...]) -> bool:
    serialized = "".join(route.model_dump_json() for route in routes).lower()
    redacted = redact_secret_spans(serialized).lower()
    return redacted == serialized and not any(marker in serialized for marker in _SECRET_MARKERS)
