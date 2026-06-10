"""Execution-integrity gate: handler-executed implies broker evidence.

The single-chokepoint invariant in one reusable, fail-closed check: if any
surface reports ``handler_executed=True`` it MUST also carry a bound broker
evidence record. A receipt that ran a handler without leaving broker evidence is
a governance breach (a back door around the dispatcher) and fails the gate.

This is the live-validation release gate (M0-5): the M1 workflow executor runs
it on every node receipt, and the release process runs it over a whole run.
"""

from __future__ import annotations

from .gate import (
    ExecutionClaim,
    ExecutionIntegrityError,
    IntegrityFinding,
    IntegrityVerdict,
    assert_claim,
    claim_from_decision_receipt,
    claim_from_provider_receipt,
    claim_violation,
    gate_executions,
)

__all__ = [
    "ExecutionClaim",
    "ExecutionIntegrityError",
    "IntegrityFinding",
    "IntegrityVerdict",
    "assert_claim",
    "claim_from_decision_receipt",
    "claim_from_provider_receipt",
    "claim_violation",
    "gate_executions",
]
