from __future__ import annotations

from zeus_agent.capability_registry_runtime import (
    CapabilityRecord,
    CapabilityStatus,
    CapabilityTrust,
    CostConfidence,
    CostModel,
    Provenance,
    SideEffectClass,
    VerbClass,
    estimate_cost_units,
    evaluate_promotion,
    import_mcp_capability,
    recompute_trust,
    reconcile_schema,
    synthesis_catalog,
)
from zeus_agent.trust_loop_runtime import Reversibility, TrustStat


def _active_builtin(capability_id: str, **overrides: object) -> CapabilityRecord:
    base: dict[str, object] = {
        "capability_id": capability_id,
        "verb_class": VerbClass.fetch,
        "title": "builtin {0}".format(capability_id),
        "input_summary": "query",
        "output_summary": "rows",
        "side_effect": SideEffectClass.none,
        "reversibility": Reversibility.reversible,
        "cost_model": CostModel(fixed_per_call_units=1.0, confidence=CostConfidence.measured),
        "trust": CapabilityTrust(score=0.9, runs=10, success_rate=0.9, measured=True),
        "provenance": Provenance.builtin,
        "status": CapabilityStatus.active,
    }
    base.update(overrides)
    return CapabilityRecord(**base)  # type: ignore[arg-type]


# --- MCP import is fail-closed ----------------------------------------------


def test_imported_mcp_tool_is_quarantined_and_conservative() -> None:
    record = import_mcp_capability(
        capability_id="mcp.unknownserver.do_thing",
        title="do thing",
        verb_class=VerbClass.publish,
        input_summary="payload",
        output_summary="ack",
        schema_hash="hash-1",
        server_ref="mcp://unknownserver",
    )
    # No estimate provided -> assume the worst.
    assert record.status is CapabilityStatus.quarantined
    assert record.side_effect is SideEffectClass.account_write
    assert record.reversibility is Reversibility.irreversible
    assert record.cost_model.confidence is CostConfidence.unknown
    assert record.trust.score == 0.0


def test_import_takes_the_more_dangerous_of_estimate_and_floor() -> None:
    # A benign estimate cannot lower the conservative floor...
    record = import_mcp_capability(
        capability_id="mcp.s.read",
        title="read",
        verb_class=VerbClass.fetch,
        input_summary="q",
        output_summary="r",
        schema_hash="h",
        server_ref="mcp://s",
        estimated_side_effect=SideEffectClass.none,
        estimated_reversibility=Reversibility.reversible,
    )
    assert record.side_effect is SideEffectClass.account_write
    assert record.reversibility is Reversibility.irreversible

    # ...but a more dangerous estimate is honoured.
    worse = import_mcp_capability(
        capability_id="mcp.s.nuke",
        title="nuke",
        verb_class=VerbClass.publish,
        input_summary="q",
        output_summary="r",
        schema_hash="h",
        server_ref="mcp://s",
        estimated_side_effect=SideEffectClass.public_write,
    )
    assert worse.side_effect is SideEffectClass.public_write


# --- Trust is earned, not granted -------------------------------------------


def test_recompute_trust_uses_laplace_smoothing() -> None:
    record = import_mcp_capability(
        capability_id="mcp.s.read",
        title="read",
        verb_class=VerbClass.fetch,
        input_summary="q",
        output_summary="r",
        schema_hash="h",
        server_ref="mcp://s",
    )
    updated = recompute_trust(record, TrustStat(capability_id="mcp.s.read", success_count=1, failure_count=1))
    # 1 success / 2 runs -> success_rate 0.5, but smoothed score (1+1)/(2+2) = 0.5
    assert updated.trust.success_rate == 0.5
    assert updated.trust.score == 0.5
    assert updated.trust.measured is True


def test_quarantined_low_risk_promotes_after_clean_runs() -> None:
    record = import_mcp_capability(
        capability_id="mcp.s.read",
        title="read",
        verb_class=VerbClass.fetch,
        input_summary="q",
        output_summary="r",
        schema_hash="h",
        server_ref="mcp://s",
    )
    record = recompute_trust(record, TrustStat(capability_id="mcp.s.read", success_count=9, failure_count=0))
    promoted = evaluate_promotion(record, human_reviewed=False)
    assert promoted.status is CapabilityStatus.active


def test_dangerous_verb_needs_human_review_to_promote() -> None:
    record = import_mcp_capability(
        capability_id="mcp.s.publish",
        title="publish",
        verb_class=VerbClass.publish,
        input_summary="q",
        output_summary="r",
        schema_hash="h",
        server_ref="mcp://s",
    )
    record = recompute_trust(record, TrustStat(capability_id="mcp.s.publish", success_count=20, failure_count=0))
    assert evaluate_promotion(record, human_reviewed=False).status is CapabilityStatus.quarantined
    assert evaluate_promotion(record, human_reviewed=True).status is CapabilityStatus.active


def test_low_trust_never_promotes() -> None:
    record = import_mcp_capability(
        capability_id="mcp.s.read",
        title="read",
        verb_class=VerbClass.fetch,
        input_summary="q",
        output_summary="r",
        schema_hash="h",
        server_ref="mcp://s",
    )
    record = recompute_trust(record, TrustStat(capability_id="mcp.s.read", success_count=2, failure_count=3))
    assert evaluate_promotion(record, human_reviewed=True).status is CapabilityStatus.quarantined


# --- Rug-pull defence -------------------------------------------------------


def test_schema_change_requarantines_and_resets_trust() -> None:
    record = _active_builtin("mcp.s.read", provenance=Provenance.mcp, schema_hash="hash-1",
                             trust=CapabilityTrust(score=0.95, runs=30, success_rate=0.95, measured=True))
    reconciled = reconcile_schema(record, "hash-2")
    assert reconciled.status is CapabilityStatus.quarantined
    assert reconciled.trust.score == 0.0
    assert reconciled.schema_hash == "hash-2"


def test_same_schema_hash_is_untouched() -> None:
    record = _active_builtin("mcp.s.read", provenance=Provenance.mcp, schema_hash="hash-1")
    assert reconcile_schema(record, "hash-1") == record


# --- Cost rollup ------------------------------------------------------------


def test_estimate_cost_rounds_up_so_plans_never_under_quote() -> None:
    model = CostModel(
        fixed_per_call_units=0.5,
        per_1k_tokens_out_units=2.0,
        confidence=CostConfidence.measured,
    )
    # 3 calls x (0.5 + 1.5*2.0) = 3 x 3.5 = 10.5 -> ceil 11
    assert estimate_cost_units(model, calls=3, tokens_out=1500) == 11


# --- Catalog projection hides nothing dangerous, leaks nothing secret -------


def test_synthesis_catalog_shows_quarantined_hides_deprecated() -> None:
    active = _active_builtin("builtin.fs.read")
    quarantined = import_mcp_capability(
        capability_id="mcp.s.read", title="read", verb_class=VerbClass.fetch,
        input_summary="q", output_summary="r", schema_hash="h", server_ref="mcp://s",
    )
    deprecated = _active_builtin("builtin.old", status=CapabilityStatus.deprecated)
    catalog = synthesis_catalog((active, quarantined, deprecated))
    ids = {entry.capability_id for entry in catalog}
    assert ids == {"builtin.fs.read", "mcp.s.read"}
    # Projection has no credential/authority fields at all.
    assert set(catalog[0].model_dump().keys()) == {
        "capability_id", "verb_class", "title", "io_summary",
        "cost_summary", "side_effect", "trust_score", "status",
    }


def test_usable_without_approval_only_for_active_no_effect() -> None:
    assert _active_builtin("a").usable_without_approval is True
    assert _active_builtin("b", side_effect=SideEffectClass.public_write).usable_without_approval is False
    assert _active_builtin("c", status=CapabilityStatus.quarantined).usable_without_approval is False
