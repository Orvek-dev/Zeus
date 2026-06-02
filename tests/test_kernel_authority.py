from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from zeus_agent.kernel.authority import (
    ApprovalReceipt,
    AuthorityContext,
    CapabilityGrant,
    CredentialGrant,
    NetworkGrant,
    PathGrant,
)
from zeus_agent.kernel.contracts import ExecutionSpec, GoalContract


def test_contract_and_execution_spec_require_acceptance_and_plan_only_default() -> None:
    contract = GoalContract(
        goal_contract_id="goal-1",
        raw_user_request="Build kernel wave 1.",
        normalized_goal="Implement kernel contract and authority models.",
        deliverables=["kernel contracts", "authority guardrails"],
        acceptance_criteria=["REQ-ZEUS-KERNEL-001:S1"],
    )
    spec = ExecutionSpec(run_id="run-1", goal_contract_id=contract.goal_contract_id)

    assert spec.execution_mode == "plan_only"

    with pytest.raises(ValidationError):
        GoalContract(
            goal_contract_id="goal-1",
            raw_user_request="Build kernel wave 1.",
            normalized_goal="Implement kernel contract and authority models.",
            deliverables=["kernel contracts"],
            acceptance_criteria=[],
        )

    with pytest.raises(ValidationError):
        GoalContract(
            goal_contract_id="goal-1",
            raw_user_request="Build kernel wave 1.",
            normalized_goal="Implement kernel contract and authority models.",
            deliverables=["kernel contracts"],
            acceptance_criteria=["REQ-ZEUS-KERNEL-001:S1"],
            extra_field=True,
        )

    with pytest.raises(ValidationError):
        ExecutionSpec(
            run_id="run-1",
            goal_contract_id="goal-1",
            unsupported=True,
        )


def test_authority_context_allows_only_unexpired_scoped_grants() -> None:
    now = datetime.now(timezone.utc)
    authority = AuthorityContext(
        principal_id="principal-a",
        run_id="run-1",
        goal_contract_id="goal-1",
        capability_grants=[
            CapabilityGrant(
                capability_id="fs.read",
                expires_at=now + timedelta(minutes=5),
            ),
        ],
        path_grants=[
            PathGrant(
                capability_id="fs.read",
                path_prefix="/workspace/read-only",
            ),
        ],
    )

    assert authority.allows(
        "fs.read",
        path="/workspace/read-only/file.txt",
        now=now,
    ).decision == "allowed"
    assert authority.allows("terminal.run", now=now).decision == "blocked"
    assert authority.allows("fs.read", path="/tmp/other.txt", now=now).decision == "blocked"

    expired = AuthorityContext(
        principal_id="principal-a",
        run_id="run-1",
        goal_contract_id="goal-1",
        capability_grants=[
            CapabilityGrant(
                capability_id="fs.read",
                expires_at=now - timedelta(seconds=1),
            ),
        ],
        path_grants=[
            PathGrant(capability_id="fs.read", path_prefix="/workspace/read-only"),
        ],
    )
    decision = expired.allows("fs.read", path="/workspace/read-only/file.txt", now=now)
    assert decision.decision == "blocked"

    missing_scope_grants = AuthorityContext(
        principal_id="principal-b",
        run_id="run-1",
        goal_contract_id="goal-1",
        capability_grants=[CapabilityGrant(capability_id="tool.exec", expires_at=now + timedelta(minutes=1))],
    )
    path_missing = missing_scope_grants.allows("tool.exec", path="/workspace/read-only/file.txt", now=now)
    assert path_missing.decision == "blocked"
    assert path_missing.reason == "path_scope_missing"

    network_missing = missing_scope_grants.allows("tool.exec", network_host="api.openai.com", now=now)
    assert network_missing.decision == "blocked"
    assert network_missing.reason == "network_scope_missing"

    credential_missing = missing_scope_grants.allows(
        "tool.exec",
        credential_scope="vault.prod",
        now=now,
    )
    assert credential_missing.decision == "blocked"
    assert credential_missing.reason == "credential_scope_missing"

    scoped = AuthorityContext(
        principal_id="principal-c",
        run_id="run-1",
        goal_contract_id="goal-1",
        capability_grants=[CapabilityGrant(capability_id="tool.exec", expires_at=now + timedelta(minutes=1))],
        path_grants=[PathGrant(capability_id="tool.exec", path_prefix="/workspace/read-only")],
        network_grants=[NetworkGrant(capability_id="tool.exec", network_host="api.openai.com")],
        credential_grants=[CredentialGrant(capability_id="tool.exec", credential_scope="vault.prod")],
    )
    assert scoped.allows("tool.exec", path="/workspace/read-only/file.txt", now=now).decision == "allowed"
    assert scoped.allows("tool.exec", network_host="api.openai.com", now=now).decision == "allowed"
    assert scoped.allows("tool.exec", credential_scope="vault.prod", now=now).decision == "allowed"


def test_approval_receipt_cannot_grant_beyond_authority_scope() -> None:
    authority = AuthorityContext(
        principal_id="principal-parent",
        run_id="run-1",
        goal_contract_id="goal-1",
        capability_grants=[CapabilityGrant(capability_id="fs.read")],
    )

    child = authority.derive_for_child(
        child_principal_id="principal-child",
        requested_capabilities=["fs.read"],
    )
    assert child.allows("fs.read").decision == "allowed"
    assert child.allows("terminal.run").decision == "blocked"

    with pytest.raises(ValueError, match="terminal.run"):
        authority.derive_for_child(
            child_principal_id="principal-child",
            requested_capabilities=["terminal.run"],
        )

    approval = ApprovalReceipt(
        principal_id="principal-parent",
        run_id="run-1",
        goal_contract_id="goal-1",
        approved_capabilities=["fs.read"],
    )
    approval.assert_within_authority(authority)

    wrong_principal = ApprovalReceipt(
        principal_id="principal-other",
        run_id="run-1",
        goal_contract_id="goal-1",
        approved_capabilities=["fs.read"],
    )
    with pytest.raises(ValueError, match="principal_id"):
        wrong_principal.assert_within_authority(authority)

    widening = ApprovalReceipt(
        principal_id="principal-parent",
        run_id="run-1",
        goal_contract_id="goal-1",
        approved_capabilities=["terminal.run"],
    )
    with pytest.raises(ValueError, match="terminal.run"):
        widening.assert_within_authority(authority)
