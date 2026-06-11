"""P6 conformance — governance UX organs.

no-template-escalates, policy-change-is-governed,
pack-onboarding-generates-rules (+ NL rules, digest/licenses, plain cards).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zeus_agent.adapters.claude_code_hook import ControlPlaneState
from zeus_agent.authority_compiler_runtime import (
    AuthorityEnvelope,
    GrantedCapability,
    GrantTier,
)
from zeus_agent.capability_registry_runtime import (
    CapabilityRecord,
    CapabilityStatus,
    CapabilityTrust,
    CostModel,
    Provenance,
    SideEffectClass,
    VerbClass,
)
from zeus_agent.consequence_runtime import explain, render_plain_card
from zeus_agent.decision_api_runtime import (
    DecisionContext,
    DecisionRequest,
    GateSurface,
    HostKind,
)
from zeus_agent.digest_runtime import ack_digest, build_digest, license_progress
from zeus_agent.graded_approval_runtime import GrantScope, issue_grant
from zeus_agent.nl_policy_runtime import apply_rule_diff, parse_nl_rule
from zeus_agent.policy_pack_runtime import apply_pack, onboarding_pack, pack_by_name
from zeus_agent.proxy_runtime import seed_proxy_capability_store
from zeus_agent.trust_loop_runtime import (
    Reversibility,
    SQLiteControlPlaneStore,
    SQLiteTrustStatStore,
    TrustDecision,
)


def _unexplained_side_effect(capability_id: str) -> CapabilityRecord:
    """A side-effecting capability with NO consequence template — the engine
    must refuse to let it run silently."""
    return CapabilityRecord(
        capability_id=capability_id,
        verb_class=VerbClass.store,
        title="Unexplained side effect",
        input_summary="x",
        output_summary="y",
        side_effect=SideEffectClass.local_write,
        reversibility=Reversibility.compensable,
        cost_model=CostModel(),
        trust=CapabilityTrust(score=0.0, runs=0, success_rate=0.0, measured=False),
        provenance=Provenance.builtin,
        status=CapabilityStatus.active,
    )


def _request(capability_id: str, session: str = "p6.sess") -> DecisionRequest:
    return DecisionRequest(
        principal_id="agent.test",
        session_id=session,
        run_id="run.p6",
        capability_id=capability_id,
        context=DecisionContext(host=HostKind.console, surface=GateSurface.console),
    )


# ------------------------------------------------------- no-template-escalates
def test_no_template_escalates_inside_decide(tmp_path: Path) -> None:
    """The rule lives in decide() now: an unexplainable side-effecting action
    becomes ASK on the receipt itself — not via a post-hoc gate mutation — and
    not even a standing license can silently cover it."""
    state = ControlPlaneState(tmp_path / "zeus")
    engine = state.build_engine(capabilities=seed_proxy_capability_store())
    far_future = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())

    # read-class with a template → AUTO. Explainability never trips a read.
    assert engine.decide(_request("fs.read")).decision is TrustDecision.AUTO

    # a templated side-effecting capability covered by a session license DOES
    # downgrade ASK→AUTO — proves the gate is specific to unexplainable ones.
    engine.grants.add(
        issue_grant(
            grant_id="grant.explained",
            capability_id="fs.write",
            scope=GrantScope.session,
            session_id="p6.sess",
            expires_at_epoch=far_future,
        )
    )
    explained = engine.decide(_request("fs.write"))
    assert explained.decision is TrustDecision.AUTO
    assert explained.reason == "covered_by_grant_session"

    # an UNEXPLAINABLE side-effecting capability granted at AUTO tier inside an
    # envelope: without the rule it would run silently. The explainability gate
    # turns the receipt ITSELF into ASK — proving the rule lives in decide(),
    # not in a post-hoc gate mutation.
    engine.capabilities.register(_unexplained_side_effect("quantum.entangle"))
    engine.envelopes.put(
        AuthorityEnvelope(
            envelope_id="env.p6",
            objective_id="obj.p6",
            principal_id="agent.test",
            granted=(
                GrantedCapability(
                    capability_id="quantum.entangle",
                    tier=GrantTier.auto,
                    provenance="obj.p6 clause",
                ),
            ),
        )
    )
    escalated = engine.decide(
        DecisionRequest(
            principal_id="agent.test",
            session_id="p6.sess",
            run_id="run.p6",
            capability_id="quantum.entangle",
            context=DecisionContext(
                host=HostKind.console,
                surface=GateSurface.console,
                objective_id="obj.p6",
            ),
        )
    )
    assert escalated.decision is TrustDecision.ASK
    assert escalated.reason == "no_plain_language_template"
    assert escalated.parked_action_id is not None  # ghost-ask killed: it parks

    # the core invariant: the ledger receipt equals the returned decision
    last = json.loads(str(engine.recorder.ledger.records()[-1]["payload_json"]))
    assert last["decision"] == "ask"
    assert last["reason"] == "no_plain_language_template"

    # explain() is the single source of truth for "is there a vetted card?"
    record = engine.capabilities.get("fs.read")
    assert record is not None
    card = explain(record, args={"path": "/work/a.py"}, provenance="목표: 소스 검토")
    assert card is not None
    rendered = render_plain_card(card, reason="tier_ask_first")
    for question in ("무엇을:", "어디에:", "되돌리기:", "왜:", "전례:"):
        assert question in rendered


# --------------------------------------------------- policy-change-is-governed
def test_policy_change_is_governed(tmp_path: Path) -> None:
    state = ControlPlaneState(tmp_path / "zeus")
    engine = state.build_engine()
    store = SQLiteControlPlaneStore(state.state_path)
    pack = pack_by_name("safe-assistant")
    assert pack is not None

    refused = apply_pack(pack, engine=engine, store=store, confirmed=False)
    assert refused["applied"] is False
    assert store.kv_get("policy.active_pack") is None, "nothing changes unconfirmed"
    assert refused["receipt_id"] is not None  # the attempt is still evidence

    applied = apply_pack(pack, engine=engine, store=store, confirmed=True)
    assert applied["applied"] is True
    decisions = [
        json.loads(str(r["payload_json"]))
        for r in engine.recorder.ledger.records()
        if json.loads(str(r["payload_json"])).get("capability_id") == "policy.change"
    ]
    assert [d["decision"] for d in decisions] == ["ask", "allow"]


# ------------------------------------------- pack-onboarding-generates-rules
def test_pack_onboarding_generates_enforced_rules(tmp_path: Path) -> None:
    state = ControlPlaneState(tmp_path / "zeus")
    engine = state.build_engine()
    store = SQLiteControlPlaneStore(state.state_path)
    pack = onboarding_pack(
        task="개발 보조", monthly_cap_usd=40.0, never_do=("payments.transfer",)
    )
    assert pack.weekly_budget_usd == 10.0
    apply_pack(pack, engine=engine, store=store, confirmed=True)

    assert store.budget_limit("fleet", "fleet") == 10_000_000  # $10/week in µUSD
    assert store.kv_get("governor.rate_max_calls") is not None

    # the never-do lock binds EVERY future gate process via persisted records
    fresh_engine = ControlPlaneState(tmp_path / "zeus").build_engine()
    denied = fresh_engine.decide(_request("payments.transfer"))
    assert denied.decision is TrustDecision.DENY
    assert denied.reason == "capability_quarantined"


# --------------------------------------------------------------- NL policy
def test_nl_rules_parse_preview_then_apply(tmp_path: Path) -> None:
    store = SQLiteControlPlaneStore(tmp_path / "state.sqlite3")

    budget = parse_nl_rule("weekly budget $12")
    assert budget is not None and budget.kind == "weekly_budget"
    apply_rule_diff(budget, store)
    assert store.budget_limit("fleet", "fleet") == 12_000_000

    rate = parse_nl_rule("분당 호출 20회")
    assert rate is not None and rate.kind == "rate"
    apply_rule_diff(rate, store)
    assert store.kv_get("governor.rate_max_calls") == "20"

    quiet = parse_nl_rule("quiet hours 22-07")
    assert quiet is not None and quiet.kind == "quiet_hours"
    apply_rule_diff(quiet, store)
    assert store.kv_get("policy.quiet_hours") == "22-07"

    tool = parse_nl_rule("mcp.files.echo 하루 5회")
    assert tool is not None and tool.kind == "tool_budget"
    apply_rule_diff(tool, store)
    assert store.budget_limit("capability", "mcp.files.echo") == 5

    assert parse_nl_rule("please be nice") is None  # outside the grammar → no guess


# ------------------------------------------------------------------- digest
def test_digest_aggregates_and_ack_resets_deadman(tmp_path: Path) -> None:
    state = ControlPlaneState(tmp_path / "zeus")
    engine = state.build_engine(capabilities=seed_proxy_capability_store())
    store = SQLiteControlPlaneStore(state.state_path)
    trust = SQLiteTrustStatStore(state.trust_path)
    engine.decide(_request("fs.read"))
    trust.upsert("mail.send", success_count=23, failure_count=0)

    now = datetime.now(timezone.utc)
    digest = build_digest(engine.recorder, store, trust, now=now)
    assert digest["decision_mix"].get("auto", 0) >= 1
    licenses = digest["licenses"]
    assert licenses and licenses[0]["license"] == "23/30"
    assert licenses[0]["licensed"] is False
    assert store.kv_get("digest.last_built") is not None

    ack_digest(store, now=now)
    assert store.kv_get("digest.last_ack") == now.isoformat()
    assert license_progress(None) == []
