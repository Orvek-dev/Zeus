from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_execution_bundle_runtime import LiveExecutionBundleResult

LiveExecutionBundleReviewDecision = Literal["review_recorded", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_REQUIRED_ACKS: Final[tuple[str, ...]] = (
    "loopback_only",
    "no_production_claim",
    "cleanup_recorded",
)


class LiveExecutionBundleReviewResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveExecutionBundleReviewDecision
    review_id: Optional[str]
    bundle_id: Optional[str]
    reviewer_id: str
    producer_id: str
    evidence_ids: tuple[str, ...]
    evidence_count: int
    risk_acknowledgements: tuple[str, ...]
    bundle_surface_count: int
    independent_review: bool = False
    cleanup_recorded: bool = False
    blocked_reasons: tuple[str, ...] = ()
    production_ready: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveExecutionBundleReviewRuntime:
    def review(
        self,
        *,
        bundle: LiveExecutionBundleResult,
        reviewer_id: str,
        producer_id: str,
        evidence_ids: tuple[str, ...],
        risk_acknowledgements: tuple[str, ...],
    ) -> LiveExecutionBundleReviewResult:
        safe_reviewer = reviewer_id.strip()
        safe_producer = producer_id.strip()
        safe_evidence = tuple(item.strip() for item in evidence_ids if item.strip())
        safe_acks = tuple(dict.fromkeys(item.strip() for item in risk_acknowledgements if item.strip()))
        independent = safe_reviewer != "" and safe_producer != "" and safe_reviewer != safe_producer
        cleanup_recorded = all(surface.cleanup_receipt for surface in bundle.surfaces)
        reasons = _review_reasons(
            bundle=bundle,
            independent=independent,
            evidence_ids=safe_evidence,
            risk_acknowledgements=safe_acks,
            cleanup_recorded=cleanup_recorded,
        )
        decision: LiveExecutionBundleReviewDecision = "blocked" if reasons else "review_recorded"
        return LiveExecutionBundleReviewResult(
            decision=decision,
            review_id=_review_id(bundle, safe_reviewer, safe_producer, safe_evidence) if decision == "review_recorded" else None,
            bundle_id=bundle.bundle_id,
            reviewer_id=safe_reviewer,
            producer_id=safe_producer,
            evidence_ids=safe_evidence,
            evidence_count=len(safe_evidence),
            risk_acknowledgements=safe_acks,
            bundle_surface_count=bundle.surface_count,
            independent_review=independent,
            cleanup_recorded=cleanup_recorded,
            blocked_reasons=reasons,
            production_ready=False,
            network_opened=False,
            handler_executed=False,
            external_delivery_opened=False,
            credential_material_accessed=False,
            raw_secret_returned=False,
            no_secret_echo=bundle.no_secret_echo,
            live_production_claimed=False,
        )


def _review_reasons(
    *,
    bundle: LiveExecutionBundleResult,
    independent: bool,
    evidence_ids: tuple[str, ...],
    risk_acknowledgements: tuple[str, ...],
    cleanup_recorded: bool,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if bundle.decision != "summarized":
        reasons.append("bundle_not_summarized")
    if bundle.bundle_id is None:
        reasons.append("bundle_id_required")
    if bundle.surface_count == 0:
        reasons.append("bundle_surface_required")
    if bundle.blocked_reasons:
        reasons.append("bundle_blocked_reasons_present")
    if not cleanup_recorded:
        reasons.append("bundle_cleanup_receipt_required")
    if not independent:
        reasons.append("independent_reviewer_required")
    if len(evidence_ids) < 2:
        reasons.append("review_evidence_ids_required")
    if bundle.non_loopback_network_opened:
        reasons.append("bundle_non_loopback_network_opened")
    if bundle.external_delivery_opened:
        reasons.append("bundle_external_delivery_opened")
    if bundle.raw_secret_returned:
        reasons.append("bundle_raw_secret_returned")
    if not bundle.no_secret_echo:
        reasons.append("bundle_secret_echo_detected")
    if bundle.live_production_claimed:
        reasons.append("bundle_live_production_claimed")
    for ack in _REQUIRED_ACKS:
        if ack not in risk_acknowledgements:
            reasons.append("risk_ack:{0}_required".format(ack))
    return tuple(dict.fromkeys(reasons))


def _review_id(
    bundle: LiveExecutionBundleResult,
    reviewer_id: str,
    producer_id: str,
    evidence_ids: tuple[str, ...],
) -> str:
    payload = {
        "bundle_id": bundle.bundle_id,
        "evidence_ids": evidence_ids,
        "producer_id": producer_id,
        "reviewer_id": reviewer_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-execution-bundle-review-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])
