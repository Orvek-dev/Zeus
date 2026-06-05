from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_execution_bundle_review_runtime import LiveExecutionBundleReviewResult
from zeus_agent.live_execution_bundle_runtime import LiveExecutionBundleResult

LiveExecutionStatusDecision = Literal["reviewed", "pending_review", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveExecutionStatusResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveExecutionStatusDecision
    status_id: Optional[str]
    bundle_id: Optional[str]
    review_id: Optional[str]
    bundle_surface_count: int = 0
    executed_count: int = 0
    credentialed_surface_count: int = 0
    review_recorded: bool = False
    independent_review: bool = False
    evidence_count: int = 0
    blocked_reasons: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...] = ()
    bundle_network_opened: bool = False
    bundle_credential_material_accessed: bool = False
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


class LiveExecutionStatusRuntime:
    def build(
        self,
        *,
        bundle: Optional[LiveExecutionBundleResult],
        review: Optional[LiveExecutionBundleReviewResult],
    ) -> LiveExecutionStatusResult:
        reasons = _status_reasons(bundle, review)
        decision = _decision(bundle, review, reasons)
        return LiveExecutionStatusResult(
            decision=decision,
            status_id=_status_id(bundle, review) if decision != "blocked" else None,
            bundle_id=None if bundle is None else bundle.bundle_id,
            review_id=None if review is None else review.review_id,
            bundle_surface_count=0 if bundle is None else bundle.surface_count,
            executed_count=0 if bundle is None else bundle.executed_count,
            credentialed_surface_count=0 if bundle is None else bundle.credentialed_surface_count,
            review_recorded=review is not None and review.decision == "review_recorded",
            independent_review=review is not None and review.independent_review,
            evidence_count=0 if review is None else review.evidence_count,
            blocked_reasons=reasons,
            recommended_next_commands=_recommended_next_commands(decision),
            bundle_network_opened=False if bundle is None else bundle.network_opened,
            bundle_credential_material_accessed=(
                False if bundle is None else bundle.credential_material_accessed
            ),
            production_ready=False,
            network_opened=False,
            handler_executed=False,
            external_delivery_opened=False,
            credential_material_accessed=False,
            raw_secret_returned=False if bundle is None else bundle.raw_secret_returned,
            no_secret_echo=_no_secret_echo(bundle, review),
            live_production_claimed=False,
        )


def _status_reasons(
    bundle: Optional[LiveExecutionBundleResult],
    review: Optional[LiveExecutionBundleReviewResult],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if bundle is None:
        reasons.append("bundle_required")
    elif bundle.decision != "summarized":
        reasons.append("bundle_not_summarized")
    if review is not None:
        if review.decision != "review_recorded":
            reasons.append("review_not_recorded")
        if bundle is not None and review.bundle_id != bundle.bundle_id:
            reasons.append("review_bundle_mismatch")
        if not review.independent_review:
            reasons.append("independent_review_required")
        if not review.no_secret_echo:
            reasons.append("review_secret_echo_detected")
    return tuple(dict.fromkeys(reasons))


def _decision(
    bundle: Optional[LiveExecutionBundleResult],
    review: Optional[LiveExecutionBundleReviewResult],
    reasons: tuple[str, ...],
) -> LiveExecutionStatusDecision:
    if reasons:
        return "blocked"
    if bundle is not None and review is None:
        return "pending_review"
    return "reviewed"


def _status_id(
    bundle: Optional[LiveExecutionBundleResult],
    review: Optional[LiveExecutionBundleReviewResult],
) -> str:
    payload = {
        "bundle_id": None if bundle is None else bundle.bundle_id,
        "review_id": None if review is None else review.review_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-execution-status-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _recommended_next_commands(decision: LiveExecutionStatusDecision) -> tuple[str, ...]:
    if decision == "pending_review":
        return ("zeus live-execution-bundle-review --json", "zeus live-readiness --json")
    if decision == "reviewed":
        return ("zeus live-readiness --json", "zeus live --include-smoke --scenario happy --json")
    return ("zeus live-execution-bundle --json", "zeus live-execution-bundle-review --json")


def _no_secret_echo(
    bundle: Optional[LiveExecutionBundleResult],
    review: Optional[LiveExecutionBundleReviewResult],
) -> bool:
    return (True if bundle is None else bundle.no_secret_echo) and (
        True if review is None else review.no_secret_echo
    )
