from __future__ import annotations

import math
from typing import Final, Optional

from zeus_agent.trust_loop_runtime import Reversibility, TrustStat

from .models import (
    CapabilityRecord,
    CapabilityStatus,
    CapabilityTrust,
    CatalogEntry,
    CostConfidence,
    CostModel,
    Provenance,
    SideEffectClass,
    VerbClass,
)

# Promotion needs a sustained clean record, not a single lucky run.
_MIN_RUNS_FOR_PROMOTION: Final = 5
_MIN_SCORE_FOR_PROMOTION: Final = 0.8

# Verb classes whose side effects are dangerous enough that a human must sign off
# before the capability leaves quarantine, no matter how good the trust score is.
_HUMAN_REVIEW_VERBS: Final = frozenset(
    {VerbClass.publish, VerbClass.notify, VerbClass.store, VerbClass.approve}
)


def import_mcp_capability(
    *,
    capability_id: str,
    title: str,
    verb_class: VerbClass,
    input_summary: str,
    output_summary: str,
    schema_hash: str,
    server_ref: str,
    estimated_side_effect: Optional[SideEffectClass] = None,
    estimated_reversibility: Optional[Reversibility] = None,
) -> CapabilityRecord:
    """Register a freshly discovered MCP tool, fail-closed.

    An unknown tool is assumed to write at account scope and be irreversible
    until proven otherwise, and always lands quarantined: visible to synthesis
    but forced through manual approval on every use.
    """
    side_effect = _max_side_effect(estimated_side_effect, SideEffectClass.account_write)
    reversibility = _max_irreversibility(estimated_reversibility, Reversibility.irreversible)
    return CapabilityRecord(
        capability_id=capability_id,
        verb_class=verb_class,
        title=title,
        input_summary=input_summary,
        output_summary=output_summary,
        side_effect=side_effect,
        reversibility=reversibility,
        cost_model=CostModel(confidence=CostConfidence.unknown),
        trust=CapabilityTrust(score=0.0, runs=0, success_rate=0.0, measured=False),
        provenance=Provenance.mcp,
        status=CapabilityStatus.quarantined,
        schema_hash=schema_hash,
        server_ref=server_ref,
    )


def recompute_trust(record: CapabilityRecord, stat: TrustStat) -> CapabilityRecord:
    """Fold ledger success/failure counts into a measured trust score.

    Uses Laplace smoothing so a 1/1 record does not read as perfect trust.
    """
    runs = stat.success_count + stat.failure_count
    success_rate = (stat.success_count / runs) if runs > 0 else 0.0
    score = (stat.success_count + 1) / (runs + 2)
    return record.model_copy(
        update={
            "trust": CapabilityTrust(
                score=round(score, 4),
                runs=runs,
                success_rate=round(success_rate, 4),
                measured=runs > 0,
            )
        }
    )


def evaluate_promotion(record: CapabilityRecord, *, human_reviewed: bool) -> CapabilityRecord:
    """Promote a quarantined capability to active only when earned.

    Trust must clear the bar; dangerous verbs additionally require a human sign
    off. Anything else stays quarantined. (Mirrors skill promotion: trust is an
    earned status, never a default.)
    """
    if record.status is not CapabilityStatus.quarantined:
        return record
    if record.trust.runs < _MIN_RUNS_FOR_PROMOTION or record.trust.score < _MIN_SCORE_FOR_PROMOTION:
        return record
    if record.verb_class in _HUMAN_REVIEW_VERBS and not human_reviewed:
        return record
    return record.model_copy(update={"status": CapabilityStatus.active})


def reconcile_schema(record: CapabilityRecord, observed_hash: str) -> CapabilityRecord:
    """Defend against MCP rug-pulls: a changed tool definition re-quarantines.

    If a server swaps its tool schema after we trusted it, the hash mismatch
    drops the capability back to quarantine and resets earned trust.
    """
    if record.schema_hash is not None and record.schema_hash == observed_hash:
        return record
    return record.model_copy(
        update={
            "schema_hash": observed_hash,
            "status": CapabilityStatus.quarantined,
            "trust": CapabilityTrust(score=0.0, runs=0, success_rate=0.0, measured=False),
        }
    )


def estimate_cost_units(
    cost_model: CostModel,
    *,
    calls: int,
    tokens_in: int = 0,
    tokens_out: int = 0,
) -> int:
    """Conservative integer budget units for a planned set of calls.

    Rounds up so a plan never under-quotes its own budget envelope.
    """
    per_call = (
        cost_model.fixed_per_call_units
        + (tokens_in / 1000.0) * cost_model.per_1k_tokens_in_units
        + (tokens_out / 1000.0) * cost_model.per_1k_tokens_out_units
    )
    return int(math.ceil(per_call * max(calls, 0)))


def catalog_entry(record: CapabilityRecord) -> CatalogEntry:
    return CatalogEntry(
        capability_id=record.capability_id,
        verb_class=record.verb_class,
        title=record.title,
        io_summary="{0} -> {1}".format(record.input_summary, record.output_summary),
        cost_summary=_cost_summary(record.cost_model),
        side_effect=record.side_effect,
        trust_score=record.trust.score,
        status=record.status,
    )


def synthesis_catalog(records: tuple[CapabilityRecord, ...]) -> tuple[CatalogEntry, ...]:
    """Catalog view for the LLM synthesiser: deprecated tools are hidden,
    quarantined ones are shown (so they can be planned behind approval)."""
    return tuple(
        catalog_entry(record)
        for record in records
        if record.status is not CapabilityStatus.deprecated
    )


_SIDE_EFFECT_RANK: Final[dict[SideEffectClass, int]] = {
    SideEffectClass.none: 0,
    SideEffectClass.local_write: 1,
    SideEffectClass.account_write: 2,
    SideEffectClass.public_write: 3,
}

_REVERSIBILITY_RANK: Final[dict[Reversibility, int]] = {
    Reversibility.reversible: 0,
    Reversibility.compensable: 1,
    Reversibility.irreversible: 2,
}


def _max_side_effect(estimate: Optional[SideEffectClass], floor: SideEffectClass) -> SideEffectClass:
    if estimate is None:
        return floor
    return estimate if _SIDE_EFFECT_RANK[estimate] >= _SIDE_EFFECT_RANK[floor] else floor


def _max_irreversibility(estimate: Optional[Reversibility], floor: Reversibility) -> Reversibility:
    if estimate is None:
        return floor
    return estimate if _REVERSIBILITY_RANK[estimate] >= _REVERSIBILITY_RANK[floor] else floor


def _cost_summary(cost_model: CostModel) -> str:
    if cost_model.confidence is CostConfidence.unknown:
        return "unmeasured (conservative estimate)"
    base = cost_model.fixed_per_call_units
    if cost_model.per_1k_tokens_out_units > 0 or cost_model.per_1k_tokens_in_units > 0:
        return "~{0} units/call + tokens ({1})".format(round(base, 2), cost_model.confidence.value)
    return "~{0} units/call ({1})".format(round(base, 2), cost_model.confidence.value)
