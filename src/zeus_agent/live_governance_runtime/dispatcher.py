from __future__ import annotations

from zeus_agent.kernel.broker import CapabilityBroker
from zeus_agent.runtime_promotion import (
    LiveTransportPromotionGuard,
    LiveTransportPromotionRequest,
    RollbackPlan,
)
from zeus_agent.workflow_runtime.jobs import RetryPolicy

from .models import GovernedLiveRequest, GovernedLiveResult, LiveCapability
from .registry import LiveCapabilityRegistry, default_live_capability_registry
from .trust import LiveGovernanceTrustStore


class GovernedLiveDispatcher:
    def __init__(
        self,
        *,
        capability_registry: LiveCapabilityRegistry | None = None,
        trust_store: LiveGovernanceTrustStore | None = None,
    ) -> None:
        self._capability_registry = capability_registry or default_live_capability_registry()
        self._trust_store = trust_store or LiveGovernanceTrustStore()

    def dispatch(self, request: GovernedLiveRequest) -> GovernedLiveResult:
        try:
            capability = self._capability_registry.require(request.capability_id)
        except KeyError:
            return GovernedLiveResult(
                decision="blocked",
                capability_id=request.capability_id,
                blocked_reasons=("capability.unknown_capability",),
                no_secret_echo=_no_secret_echo(
                    request,
                    ("capability.unknown_capability",),
                ),
            )
        preflight_reasons = _preflight_reasons(request, capability)
        if preflight_reasons:
            return GovernedLiveResult(
                decision="blocked",
                capability_id=request.capability_id,
                blocked_reasons=preflight_reasons,
                lease_bound=request.lease_ref is not None,
                approval_bound=request.approval_ref is not None,
                promotion_guard_bound=request.promotion_guard_ref is not None,
                broker_evidence_bound=False,
                no_secret_echo=_no_secret_echo(request, preflight_reasons),
                raw_secret_returned=False,
            )

        record = self._trust_store.resolve(
            capability_id=request.capability_id,
            lease_ref=request.lease_ref or "",
            approval_ref=request.approval_ref or "",
            promotion_guard_ref=request.promotion_guard_ref or "",
            broker_evidence_ref=request.broker_evidence_ref or "",
        )
        if record is None:
            return GovernedLiveResult(
                decision="blocked",
                capability_id=request.capability_id,
                blocked_reasons=("trust_store.missing_trusted_governance_record",),
                lease_bound=False,
                approval_bound=False,
                promotion_guard_bound=False,
                broker_evidence_bound=False,
                no_secret_echo=True,
            )

        promotion = LiveTransportPromotionGuard(live_transport_enabled=True).evaluate(
            _promotion_request(request),
            authority=record.authority,
            approval_receipt=record.approval,
        )
        if promotion.decision == "blocked":
            return GovernedLiveResult(
                decision="blocked",
                capability_id=request.capability_id,
                blocked_reasons=("promotion_guard.{0}".format(promotion.reason),),
                lease_bound=True,
                approval_bound=True,
                promotion_guard_bound=True,
                broker_evidence_bound=False,
                no_secret_echo=True,
            )

        broker = CapabilityBroker(
            self._capability_registry.to_capability_graph(),
            handlers={
                capability.capability_id: _local_smoke_handler,
            },
        )
        broker_response = broker.dispatch(
            request.capability_id,
            {
                "provider": request.provider,
                "scenario": request.scenario,
                "credential_scope": request.credential_scope,
                "network_host": request.network_host,
            },
            record.authority,
            approval_receipts=[record.approval],
            criterion_id="REQ-ZEUS-KERNEL-006:S1",
        )
        evidence = broker_response.get("evidence")
        evidence_status = evidence.get("status") if isinstance(evidence, dict) else None
        evidence_type = evidence.get("evidence_type") if isinstance(evidence, dict) else None
        decision = broker_response.get("decision")
        allowed = decision == "allowed" and evidence is not None
        if allowed:
            return GovernedLiveResult(
                decision="allowed",
                capability_id=request.capability_id,
                handler_executed=True,
                lease_bound=True,
                approval_bound=True,
                promotion_guard_bound=True,
                broker_evidence_bound=True,
                no_secret_echo=True,
                broker_decision="allowed",
                broker_evidence_status=evidence_status,
                broker_evidence_type=evidence_type,
            )
        return GovernedLiveResult(
            decision="blocked",
            capability_id=request.capability_id,
            blocked_reasons=("broker.{0}".format(broker_response.get("reason", "blocked")),),
            lease_bound=True,
            approval_bound=True,
            promotion_guard_bound=True,
            broker_evidence_bound=evidence is not None,
            no_secret_echo=True,
            broker_decision=str(decision),
            broker_evidence_status=evidence_status,
            broker_evidence_type=evidence_type,
        )


def _preflight_reasons(
    request: GovernedLiveRequest,
    capability: LiveCapability,
) -> tuple[str, ...]:
    reasons = []
    if request.provider != capability.provider:
        reasons.append("provider.untrusted_provider")
    if request.scenario != capability.scenario:
        reasons.append("scenario.untrusted_scenario")
    if request.lease_ref is None:
        reasons.append("lease.missing_lease")
    elif request.lease_ref != capability.lease_ref:
        reasons.append("lease.untrusted_lease")
    if request.approval_ref is None:
        reasons.append("approval.missing_approval")
    elif request.approval_ref != capability.approval_ref:
        reasons.append("approval.untrusted_approval")
    if request.promotion_guard_ref is None:
        reasons.append("promotion_guard.missing_promotion_guard")
    elif request.promotion_guard_ref != capability.promotion_guard_ref:
        reasons.append("promotion_guard.untrusted_promotion_guard")
    if request.broker_evidence_ref is None:
        reasons.append("broker_evidence.missing_broker_evidence_ref")
    elif request.broker_evidence_ref != capability.broker_evidence_ref:
        reasons.append("broker_evidence.untrusted_broker_evidence_ref")
    if request.credential_scope != capability.credential_scope:
        reasons.append("credential_scope.untrusted_credential_scope")
    if request.network_host is not None and request.network_host not in capability.network_hosts:
        reasons.append("network_scope.untrusted_network_host")
    if request.raw_credential is not None:
        reasons.append("credential.raw_secret_raw_credential_blocked")
    return tuple(reasons)


def _promotion_request(request: GovernedLiveRequest) -> LiveTransportPromotionRequest:
    return LiveTransportPromotionRequest(
        promotion_id=request.promotion_guard_ref or "promotion-guard.missing",
        capability_id=request.capability_id,
        transport_kind="provider",
        idempotency_key="v210-{0}".format(request.scenario.replace("-", ".")),
        retry_policy=RetryPolicy(max_attempts=1, backoff_seconds=0),
        rollback_plan=RollbackPlan(command="noop", target=request.capability_id),
        credential_scope=request.credential_scope,
        network_host=request.network_host,
    )


def _local_smoke_handler(payload: dict) -> dict:
    return {
        "status": "ok",
        "provider": payload.get("provider"),
        "scenario": payload.get("scenario"),
    }


def _no_secret_echo(request: GovernedLiveRequest, reasons: tuple[str, ...]) -> bool:
    serialized = GovernedLiveResult(
        decision="blocked",
        capability_id=request.capability_id,
        blocked_reasons=reasons,
    ).model_dump_json()
    return request.raw_credential is None or request.raw_credential not in serialized
