from __future__ import annotations

from typing import Optional

from .models import RiskClass, RiskContext, Unknown

# --- Per-unknown hard rules: fail-closed, override-locked --------------------
#
# These fire regardless of the VoI score and CANNOT be waived by a "just do it"
# override. Their job is to make "act on an unspecified external target" or
# "spend with no ceiling" structurally impossible.


def hard_question_reason(unknown: Unknown) -> Optional[str]:
    """Return a lock reason if this unknown must be a question no matter the VoI."""
    if unknown.risk_class is RiskClass.external and unknown.safe_default is None:
        # The only "default" for an external effect is to turn it off (local
        # only). That is a product decision, never a silent assumption.
        return "external_effect_target_unspecified"
    if unknown.risk_class is RiskClass.cost and unknown.safe_default is None:
        return "cost_cap_unspecified"
    if (
        unknown.risk_class is RiskClass.data
        and unknown.sensitive
        and unknown.feeds_external_sink
    ):
        # R2 as a hard lock: a sensitive-data -> external-sink path is the data
        # leak path; it can never be assumed away.
        return "sensitive_data_flows_to_external_sink"
    if (
        unknown.risk_class in {RiskClass.external, RiskClass.access}
        and unknown.multiple_account_candidates
    ):
        # R3: more than one account/credential could satisfy the action; guessing
        # the wrong one is an account-level mistake.
        return "ambiguous_account_for_external_effect"
    return None


# --- Workflow-level cross-class escalations ---------------------------------
#
# These depend on numeric context (projected cost vs cap, sample cost) rather
# than a single unknown, so they are applied after per-unknown classification.


def time_breaches_budget(context: RiskContext) -> bool:
    """R1: periodicity x per-run cost overruns the cap -> escalate time unknowns."""
    if context.budget_cap_units is None:
        return False
    return context.projected_cost_units > context.budget_cap_units


def sample_cost_exceeds_cap(context: RiskContext) -> bool:
    """R4: a learn-by-sample probe that itself costs more than one run allows."""
    cap = context.budget_cap_units if context.budget_cap_units is not None else context.single_run_cap_units
    return context.sample_cost_units > cap
