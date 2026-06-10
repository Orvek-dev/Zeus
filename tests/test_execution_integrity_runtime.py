from __future__ import annotations

import pytest

from zeus_agent.execution_integrity_runtime import (
    ExecutionClaim,
    ExecutionIntegrityError,
    assert_claim,
    claim_from_decision_receipt,
    claim_from_provider_receipt,
    claim_violation,
    gate_executions,
)
from zeus_agent.provider_capability_runtime import (
    CanonicalProviderHandler,
    ProviderRequest,
    ProviderVendor,
)
from zeus_agent.trust_loop_runtime import SQLiteEvidenceLedger


def _claim(surface: str, **overrides: object) -> ExecutionClaim:
    base: dict[str, object] = {
        "surface": surface,
        "handler_executed": True,
        "broker_evidence_bound": True,
        "evidence_record_id": "trust.ev.000001",
    }
    base.update(overrides)
    return ExecutionClaim(**base)  # type: ignore[arg-type]


# --- The invariant ----------------------------------------------------------


def test_executed_with_broker_evidence_is_clean() -> None:
    assert claim_violation(_claim("ok")) is None


def test_executed_without_broker_evidence_is_a_breach() -> None:
    claim = _claim("backdoor", broker_evidence_bound=False)
    assert claim_violation(claim) == "handler_executed_without_broker_evidence"


def test_executed_without_evidence_record_is_a_breach() -> None:
    claim = _claim("backdoor", evidence_record_id=None)
    assert claim_violation(claim) == "handler_executed_without_evidence_record"


def test_not_executed_is_always_fine() -> None:
    claim = _claim("blocked", handler_executed=False, broker_evidence_bound=False, evidence_record_id=None)
    assert claim_violation(claim) is None


# --- The gate over a set ----------------------------------------------------


def test_gate_fails_closed_on_any_breach() -> None:
    verdict = gate_executions(
        (
            _claim("a"),
            _claim("b", broker_evidence_bound=False),
            _claim("c"),
        )
    )
    assert verdict.ok is False
    assert verdict.checked == 3
    assert {f.surface for f in verdict.findings} == {"b"}


def test_gate_passes_when_all_clean() -> None:
    verdict = gate_executions((_claim("a"), _claim("b")))
    assert verdict.ok is True
    assert verdict.findings == ()


# --- Adapters bind real receipts to the gate --------------------------------


def test_real_provider_receipt_passes_the_gate(tmp_path) -> None:
    ledger = SQLiteEvidenceLedger(tmp_path / "ev.sqlite3")
    handler = CanonicalProviderHandler(ledger=ledger)
    receipt = handler.generate(
        ProviderRequest(vendor=ProviderVendor.fake, model_id="m", message="hi")
    )
    claim = claim_from_provider_receipt(receipt)
    # A real executed provider call leaves broker evidence → passes the gate.
    assert claim.handler_executed is True
    assert claim_violation(claim) is None


def test_assert_claim_raises_on_breach() -> None:
    # The inline enforcement surfaces (e.g. the provider handler) call assert_claim
    # and must fail loud on a chokepoint breach.
    clean = _claim("ok")
    assert assert_claim(clean) is None
    with pytest.raises(ExecutionIntegrityError):
        assert_claim(_claim("backdoor", broker_evidence_bound=False))


def test_provider_handler_enforces_the_gate_inline(tmp_path) -> None:
    # A real provider call returns a receipt that passes the gate (proves the
    # handler's inline assert_claim did not raise on the happy path).
    from zeus_agent.provider_capability_runtime import (
        CanonicalProviderHandler,
        ProviderRequest,
        ProviderVendor,
    )
    from zeus_agent.trust_loop_runtime import SQLiteEvidenceLedger

    handler = CanonicalProviderHandler(ledger=SQLiteEvidenceLedger(tmp_path / "ev.sqlite3"))
    receipt = handler.generate(
        ProviderRequest(vendor=ProviderVendor.fake, model_id="m", message="hi")
    )
    assert claim_violation(claim_from_provider_receipt(receipt)) is None


def test_decision_receipt_adapter_reads_fields() -> None:
    class _FakeReceipt:
        handler_executed = True
        broker_evidence_bound = False
        evidence_record_id = "x"

    claim = claim_from_decision_receipt(_FakeReceipt(), surface="trust_loop")
    assert claim.surface == "trust_loop"
    assert claim_violation(claim) == "handler_executed_without_broker_evidence"
