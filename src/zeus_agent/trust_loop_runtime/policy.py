from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .models import ActionRisk, Reversibility, TrustDecision, TrustLoopAction, TrustPolicyProfile


class TrustPolicyOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: TrustDecision
    reason: str


class TrustDecisionEngine:
    def __init__(self, profile: TrustPolicyProfile = TrustPolicyProfile.cautious) -> None:
        self._profile = profile

    def evaluate(
        self,
        action: TrustLoopAction,
        *,
        approval_bound: bool,
        undo_proven: bool,
    ) -> TrustPolicyOutcome:
        if action.budget.requested_units > action.budget.max_units:
            return TrustPolicyOutcome(decision=TrustDecision.ASK, reason="budget_breach")
        if _must_ask_for_taint(action):
            return TrustPolicyOutcome(
                decision=TrustDecision.ASK,
                reason="tainted_medium_risk_requires_approval",
            )
        if action.reversibility is Reversibility.irreversible:
            return _approval_outcome(approval_bound=approval_bound, reason="approval_required")
        if action.risk is ActionRisk.high:
            if not approval_bound:
                return TrustPolicyOutcome(decision=TrustDecision.ASK, reason="approval_required")
            if not undo_proven and action.reversibility is not Reversibility.irreversible:
                return TrustPolicyOutcome(decision=TrustDecision.ASK, reason="undo_plan_required")
            return TrustPolicyOutcome(decision=TrustDecision.ASK, reason="approved_high_risk")
        if action.risk is ActionRisk.medium:
            return self._medium_risk_outcome(action, undo_proven=undo_proven)
        return TrustPolicyOutcome(decision=TrustDecision.AUTO, reason="low_risk_auto")

    def _medium_risk_outcome(
        self,
        action: TrustLoopAction,
        *,
        undo_proven: bool,
    ) -> TrustPolicyOutcome:
        if self._profile is TrustPolicyProfile.cautious:
            return TrustPolicyOutcome(decision=TrustDecision.ASK, reason="cautious_medium_risk")
        if action.reversibility is Reversibility.reversible:
            return TrustPolicyOutcome(decision=TrustDecision.NOTIFY, reason="medium_risk_notify")
        if undo_proven:
            return TrustPolicyOutcome(decision=TrustDecision.NOTIFY, reason="medium_risk_notify")
        return TrustPolicyOutcome(decision=TrustDecision.ASK, reason="undo_plan_required")


def _must_ask_for_taint(action: TrustLoopAction) -> bool:
    if not action.tainted or not action.taint_sensitive:
        return False
    return action.risk in {ActionRisk.medium, ActionRisk.high}


def _approval_outcome(*, approval_bound: bool, reason: str) -> TrustPolicyOutcome:
    if approval_bound:
        return TrustPolicyOutcome(decision=TrustDecision.ASK, reason="approved_irreversible")
    return TrustPolicyOutcome(decision=TrustDecision.ASK, reason=reason)
