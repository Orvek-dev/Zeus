from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from zeus_agent.runtime_lease import RuntimeIntakeRequest, RuntimeLease, RuntimeLeaseBuilder
from zeus_agent.security.credentials import redact_secret_spans

GatewayDraftDecision = Literal["drafted", "recorded", "blocked"]


@dataclass(frozen=True)
class GatewayDraftRequest:
    request_id: str
    capability_id: str
    route: str
    method: str
    body: str
    live_network: bool = False
    network_host: str | None = None


@dataclass(frozen=True)
class GatewayDraftRecord:
    request_id: str
    capability_id: str
    route: str
    method: str
    redacted_body: str
    draft_only: bool
    live_network: bool


@dataclass(frozen=True)
class GatewayDraftResult:
    decision: GatewayDraftDecision
    reason: str
    record: GatewayDraftRecord | None
    handler_executed: bool = False
    network_opened: bool = False


def create_gateway_draft(
    *,
    request: GatewayDraftRequest,
    lease: RuntimeLease | None,
    now: datetime,
) -> GatewayDraftResult:
    authorized = RuntimeLeaseBuilder().authorize(
        lease,
        RuntimeIntakeRequest(
            runtime_kind="gateway",
            capability_id=request.capability_id,
            network_host=request.network_host,
            live_network=request.live_network,
            budget_required=1,
            evidence_target="mneme.wave13.production",
        ),
        now=now,
    )
    if authorized.decision == "blocked":
        return GatewayDraftResult(
            decision="blocked",
            reason=authorized.reason,
            record=None,
        )
    return GatewayDraftResult(
        decision="drafted",
        reason="gateway_draft_created",
        record=_record(request),
    )


def record_api_draft_execution(
    *,
    request: GatewayDraftRequest,
    lease: RuntimeLease | None,
    now: datetime,
) -> GatewayDraftResult:
    authorized = RuntimeLeaseBuilder().authorize(
        lease,
        RuntimeIntakeRequest(
            runtime_kind="api_tool",
            capability_id=request.capability_id,
            network_host=request.network_host,
            live_network=request.live_network,
            budget_required=1,
            evidence_target="mneme.wave13.production",
        ),
        now=now,
    )
    if authorized.decision == "blocked":
        return GatewayDraftResult(
            decision="blocked",
            reason=authorized.reason,
            record=None,
        )
    return GatewayDraftResult(
        decision="recorded",
        reason="api_draft_execution_recorded",
        record=_record(request),
    )


def _record(request: GatewayDraftRequest) -> GatewayDraftRecord:
    return GatewayDraftRecord(
        request_id=redact_secret_spans(request.request_id),
        capability_id=request.capability_id,
        route=redact_secret_spans(request.route),
        method=request.method.upper(),
        redacted_body=redact_secret_spans(request.body),
        draft_only=True,
        live_network=request.live_network,
    )
