from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator

from zeus_agent.runtime_lease.models import RuntimeLease
from zeus_agent.security.credentials import redact_secret_spans

LiveSurfaceKind = Literal[
    "provider",
    "mcp",
    "web",
    "gateway",
    "network",
    "plugin",
    "live_sandbox",
    "local",
    "research",
    "ontology",
    "orchestration",
    "sandbox",
]
SecurityPlanningDecision = Literal["allowed", "blocked"]
SecurityPlanReason = Literal[
    "allowed",
    "dry_run",
    "missing_runtime_lease",
    "malformed_runtime_lease",
    "unsafe_credential_scope",
    "scope_mismatch",
    "live_transport_not_authorized",
]

_SAFE_SURFACES: Final[frozenset[LiveSurfaceKind]] = frozenset(
    ("local", "research", "ontology", "orchestration", "sandbox"),
)
_ALLOWED_CAPABILITY_PREFIXES: Final[tuple[str, ...]] = (
    "provider.",
    "mcp.",
    "web.",
    "gateway.",
    "network.",
    "plugin.",
    "live_sandbox.",
    "local.",
    "research.",
    "ontology.",
    "orchestration.",
    "sandbox.",
)
_SURFACE_CAPABILITY_PREFIX: Final[dict[LiveSurfaceKind, str]] = {
    "provider": "provider.",
    "mcp": "mcp.",
    "web": "web.",
    "gateway": "gateway.",
    "network": "network.",
    "plugin": "plugin.",
    "live_sandbox": "live_sandbox.",
    "local": "local.",
    "research": "research.",
    "ontology": "ontology.",
    "orchestration": "orchestration.",
    "sandbox": "sandbox.",
}


class SecurityPlanningRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    surface_kind: LiveSurfaceKind
    capability_id: str
    requested_scope: Optional[str] = None
    network_host: Optional[str] = None
    dry_run: bool = False
    evidence_target: Optional[str] = None

    @field_validator("capability_id")
    @classmethod
    def _validate_capability_id(cls, value: str) -> str:
        normalized = value.strip()
        if normalized == "":
            raise ValueError("capability_id_empty")
        if not any(
            normalized.startswith(prefix) for prefix in _ALLOWED_CAPABILITY_PREFIXES
        ):
            raise ValueError("malformed_capability_id")
        return normalized

    @field_validator("network_host", "requested_scope", "evidence_target")
    @classmethod
    def _validate_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        if normalized == "":
            return None
        return normalized


class SecurityPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    decision: SecurityPlanningDecision
    reason: SecurityPlanReason
    surface_kind: LiveSurfaceKind
    capability_id: str
    dry_run: bool
    redacted_input: Optional[str] = None
    handler_executed: bool = False
    network_opened: bool = False
    no_secret_echo: bool = True
    scope_matched: bool = False


class SecurityPlanBuilder:
    def build(
        self,
        request: SecurityPlanningRequest,
        *,
        runtime_lease: Optional[RuntimeLease] = None,
    ) -> SecurityPlan:
        redacted_scope = _redact_if_needed(request.requested_scope)
        if request.requested_scope is not None and redacted_scope != request.requested_scope:
            return _blocked(
                request,
                "unsafe_credential_scope",
                redacted_input=redacted_scope,
            )

        if not request.capability_id.startswith(
            _SURFACE_CAPABILITY_PREFIX[request.surface_kind],
        ):
            return _blocked(request, "scope_mismatch")

        if request.surface_kind in _SAFE_SURFACES:
            return _allowed(
                request,
                "dry_run" if request.dry_run else "allowed",
                scope_matched=False,
            )

        if runtime_lease is None:
            if request.dry_run:
                return _allowed(request, "dry_run", scope_matched=False)
            return _blocked(request, "missing_runtime_lease")

        if not isinstance(runtime_lease, RuntimeLease):
            return _blocked(request, "malformed_runtime_lease")

        if request.capability_id not in set(runtime_lease.allowed_capabilities):
            return _blocked(request, "scope_mismatch")
        if request.network_host is not None and request.network_host not in set(
            runtime_lease.network_hosts,
        ):
            return _blocked(request, "scope_mismatch")
        if request.requested_scope is not None and request.requested_scope not in set(
            runtime_lease.credential_scopes,
        ):
            return _blocked(request, "scope_mismatch")

        if not request.dry_run and not runtime_lease.live_transport_allowed:
            return _blocked(request, "live_transport_not_authorized")

        reason = "dry_run" if request.dry_run else "allowed"
        return _allowed(request, reason, scope_matched=True)


def _allowed(
    request: SecurityPlanningRequest,
    reason: str,
    *,
    scope_matched: bool,
    redacted_input: Optional[str] = None,
) -> SecurityPlan:
    return SecurityPlan(
        decision="allowed" if reason in {"allowed", "dry_run"} else "blocked",
        reason=reason,
        surface_kind=request.surface_kind,
        capability_id=request.capability_id,
        dry_run=request.dry_run,
        scope_matched=scope_matched,
        redacted_input=redacted_input,
    )


def _blocked(
    request: SecurityPlanningRequest,
    reason: str,
    *,
    redacted_input: Optional[str] = None,
) -> SecurityPlan:
    return SecurityPlan(
        decision="blocked",
        reason=reason,
        surface_kind=request.surface_kind,
        capability_id=request.capability_id,
        dry_run=request.dry_run,
        redacted_input=redacted_input,
        scope_matched=False,
    )


def _redact_if_needed(raw_scope: Optional[str]) -> Optional[str]:
    if raw_scope is None:
        return None
    return redact_secret_spans(raw_scope)
