from __future__ import annotations

from zeus_agent.capability_registry_runtime import SideEffectClass, import_mcp_capability, VerbClass
from zeus_agent.taint_runtime import (
    SessionTaintTracker,
    TaintLabel,
    assess_action,
    is_external_send,
    is_untrusted_source,
)
from zeus_agent.trust_loop_runtime import TrustDecision

SESSION = "session.taint.test"


def _mcp_record():
    return import_mcp_capability(
        capability_id="custom.tool.call",
        title="Custom tool",
        verb_class=VerbClass.fetch,
        input_summary="query",
        output_summary="result",
        schema_hash="hash-1",
        server_ref="server.local",
    )


def test_web_fetch_stamps_untrusted() -> None:
    tracker = SessionTaintTracker()
    stamps = tracker.observe_capability(SESSION, "web.fetch")
    assert [stamp.label for stamp in stamps] == [TaintLabel.untrusted]
    assert TaintLabel.untrusted in tracker.labels(SESSION)


def test_mcp_provenance_is_untrusted_even_without_prefix() -> None:
    assert is_untrusted_source("custom.tool.call", _mcp_record())
    assert not is_untrusted_source("custom.tool.call", None)


def test_secret_read_stamps_private() -> None:
    tracker = SessionTaintTracker()
    tracker.observe_capability(SESSION, "secret.read")
    assert TaintLabel.private in tracker.labels(SESSION)


def test_labels_persist_until_sanitized() -> None:
    tracker = SessionTaintTracker()
    tracker.observe_capability(SESSION, "web.fetch")
    tracker.observe_capability(SESSION, "secret.read")
    assert tracker.labels(SESSION) == frozenset({TaintLabel.untrusted, TaintLabel.private})
    removed = tracker.sanitize(SESSION, TaintLabel.untrusted)
    assert removed == 1
    assert tracker.labels(SESSION) == frozenset({TaintLabel.private})
    tracker.sanitize(SESSION)
    assert tracker.labels(SESSION) == frozenset()


def test_trifecta_rule_1_untrusted_to_external_sink_forces_ask() -> None:
    assessment = assess_action(
        live_labels={TaintLabel.untrusted},
        side_effect=SideEffectClass.account_write,
    )
    assert assessment.forced_decision is TrustDecision.ASK
    assert assessment.tainted and assessment.taint_sensitive


def test_trifecta_rule_1_local_write_is_not_forced() -> None:
    assessment = assess_action(
        live_labels={TaintLabel.untrusted},
        side_effect=SideEffectClass.local_write,
    )
    assert assessment.forced_decision is None


def test_trifecta_rule_2_private_to_unapproved_host_denies() -> None:
    assessment = assess_action(
        live_labels={TaintLabel.private},
        side_effect=SideEffectClass.account_write,
        network_host="evil.example.com",
        approved_hosts=("api.github.com",),
    )
    assert assessment.forced_decision is TrustDecision.DENY
    assert "private_taint_to_unapproved_host" in assessment.reasons


def test_trifecta_rule_2_approved_host_passes() -> None:
    assessment = assess_action(
        live_labels={TaintLabel.private},
        side_effect=SideEffectClass.account_write,
        network_host="api.github.com",
        approved_hosts=("api.github.com",),
    )
    assert assessment.forced_decision is None


def test_trifecta_rule_3_credential_plus_send_escalates() -> None:
    assessment = assess_action(
        live_labels=set(),
        side_effect=SideEffectClass.account_write,
        credential_access=True,
        external_send=True,
    )
    assert assessment.risk_escalation == 1
    assert assessment.forced_decision is None


def test_anti_goodhart_ledger_read_taints_untrusted() -> None:
    tracker = SessionTaintTracker()
    stamp = tracker.stamp_ledger_read(SESSION, "trust.ev.000007")
    assert stamp.label is TaintLabel.untrusted
    assert stamp.provenance == "ledger_read:trust.ev.000007"
    assert TaintLabel.untrusted in tracker.labels(SESSION)


def test_external_send_classification() -> None:
    assert is_external_send("mail.send")
    assert is_external_send("fs.write", network_host="api.example.com")
    assert not is_external_send("fs.write")
