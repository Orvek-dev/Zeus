from __future__ import annotations

from typing import Final, Literal, Protocol

from pydantic import BaseModel, ConfigDict, field_validator

from zeus_agent.security.credentials import redact_secret_spans

DispatchDecision = Literal["planned", "blocked"]

_STRICT_MODEL: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class RuntimeLeaseLike(Protocol):
    lease_id: str
    allowed_capabilities: tuple[str, ...]
    network_hosts: tuple[str, ...]
    live_transport_allowed: bool


class EvidenceObligation(BaseModel):
    model_config = _STRICT_MODEL

    required: bool
    target: str | None = None
    reason: str


class CleanupObligation(BaseModel):
    model_config = _STRICT_MODEL

    required: bool
    reason: str


class BrowserDispatchRequest(BaseModel):
    model_config = _STRICT_MODEL

    request_id: str = "browser.dispatch"
    target_url: str
    dry_run: bool = True
    capability_id: str = "browser.navigate.plan"
    network_host: str | None = None
    approval_receipt_id: str | None = None
    evidence_target: str | None = None
    lease_id: str | None = None

    @field_validator(
        "request_id",
        "target_url",
        "capability_id",
        "network_host",
        "approval_receipt_id",
        "evidence_target",
        "lease_id",
    )
    @classmethod
    def _validate_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        redacted = redact_secret_spans(value.strip())
        if not redacted:
            raise ValueError("empty_browser_dispatch_field")
        return redacted


class BrowserDispatchResult(BaseModel):
    model_config = _STRICT_MODEL

    decision: DispatchDecision
    reason: str
    request_id: str
    capability_id: str
    target_url: str
    dry_run: bool
    blocked_reasons: tuple[str, ...] = ()
    evidence_obligation: EvidenceObligation
    cleanup_obligation: CleanupObligation
    handler_executed: bool = False
    network_opened: bool = False
    no_secret_echo: bool = True


class BrowserDispatchFacade:
    def plan(
        self,
        request: BrowserDispatchRequest,
        runtime_lease: RuntimeLeaseLike | None = None,
    ) -> BrowserDispatchResult:
        if request.dry_run:
            return _result(request, decision="planned", reasons=("dry_run_plan_only",))
        reasons = _live_block_reasons(request, runtime_lease)
        return _result(request, decision="blocked", reasons=reasons)


BrowserDispatchPlanner = BrowserDispatchFacade
BrowserFacade = BrowserDispatchFacade


def plan_browser_dispatch(
    request: BrowserDispatchRequest | str,
    *,
    dry_run: bool = True,
    runtime_lease: RuntimeLeaseLike | None = None,
    approval_receipt_id: str | None = None,
    evidence_target: str | None = None,
) -> BrowserDispatchResult:
    match request:
        case BrowserDispatchRequest():
            dispatch_request = request
        case str():
            dispatch_request = BrowserDispatchRequest(
                target_url=request,
                dry_run=dry_run,
                approval_receipt_id=approval_receipt_id,
                evidence_target=evidence_target,
            )
        case unreachable:
            raise TypeError(f"unsupported_browser_dispatch_request:{type(unreachable).__name__}")
    return BrowserDispatchFacade().plan(dispatch_request, runtime_lease=runtime_lease)


def _live_block_reasons(
    request: BrowserDispatchRequest,
    runtime_lease: RuntimeLeaseLike | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if runtime_lease is None:
        reasons.append("missing_runtime_lease")
    if request.approval_receipt_id is None:
        reasons.append("missing_approval")
    if request.evidence_target is None:
        reasons.append("missing_evidence")
    if runtime_lease is not None:
        reasons.extend(_lease_reasons(request, runtime_lease))
    reasons.append("live_navigation_not_supported")
    return tuple(_unique(reasons))


def _lease_reasons(
    request: BrowserDispatchRequest,
    runtime_lease: RuntimeLeaseLike,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if request.capability_id not in runtime_lease.allowed_capabilities:
        reasons.append("capability_not_allowed")
    if request.network_host is not None and request.network_host not in runtime_lease.network_hosts:
        reasons.append("network_host_mismatch")
    if not runtime_lease.live_transport_allowed:
        reasons.append("live_transport_disallowed")
    return tuple(reasons)


def _result(
    request: BrowserDispatchRequest,
    *,
    decision: DispatchDecision,
    reasons: tuple[str, ...],
) -> BrowserDispatchResult:
    return BrowserDispatchResult(
        decision=decision,
        reason=";".join(reasons),
        request_id=request.request_id,
        capability_id=request.capability_id,
        target_url=request.target_url,
        dry_run=request.dry_run,
        blocked_reasons=() if decision == "planned" else reasons,
        evidence_obligation=EvidenceObligation(
            required=True,
            target=request.evidence_target,
            reason="browser_dispatch_requires_evidence",
        ),
        cleanup_obligation=CleanupObligation(
            required=False,
            reason="browser_facade_allocates_no_local_resources",
        ),
    )


def _unique(values: list[str]) -> tuple[str, ...]:
    unique: list[str] = []
    for value in values:
        if value not in unique:
            unique.append(value)
    return tuple(unique)


__all__: Final = (
    "BrowserDispatchFacade",
    "BrowserDispatchPlanner",
    "BrowserDispatchRequest",
    "BrowserDispatchResult",
    "BrowserFacade",
    "CleanupObligation",
    "DispatchDecision",
    "EvidenceObligation",
    "plan_browser_dispatch",
)
