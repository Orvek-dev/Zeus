from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from zeus_agent.kernel.authority import (
    AuthorityContext,
    CapabilityGrant,
    CredentialGrant,
    NetworkGrant,
    PathGrant,
)


def test_child_authority_cannot_exceed_parent_capabilities() -> None:
    now = datetime.now(timezone.utc)
    parent = AuthorityContext(
        principal_id="parent",
        run_id="run-v210",
        goal_contract_id="goal-v210",
        capability_grants=[
            CapabilityGrant(
                capability_id="provider.local-smoke",
                expires_at=now + timedelta(minutes=5),
            ),
        ],
        path_grants=[PathGrant(capability_id="provider.local-smoke", path_prefix="/foo/bar")],
        network_grants=[
            NetworkGrant(capability_id="provider.local-smoke", network_host="127.0.0.1"),
        ],
        credential_grants=[
            CredentialGrant(
                capability_id="provider.local-smoke",
                credential_scope="credential.local-smoke",
            ),
        ],
    )

    child = parent.derive_for_child(
        child_principal_id="child",
        requested_capabilities=["provider.local-smoke"],
    )

    assert child.allows("provider.local-smoke", path="/foo/bar/run.log", now=now).decision == "allowed"
    assert child.allows("terminal.execute", now=now).decision == "blocked"
    assert child.allows(
        "provider.local-smoke",
        network_host="api.example.com",
        now=now,
    ).decision == "blocked"
    assert child.allows(
        "provider.local-smoke",
        credential_scope="credential.production",
        now=now,
    ).decision == "blocked"
    with pytest.raises(ValueError, match="terminal.execute"):
        parent.derive_for_child(
            child_principal_id="widening-child",
            requested_capabilities=["provider.local-smoke", "terminal.execute"],
        )


def test_path_scope_requires_directory_boundary_not_prefix_match() -> None:
    authority = AuthorityContext(
        principal_id="principal",
        run_id="run-v210",
        goal_contract_id="goal-v210",
        capability_grants=[CapabilityGrant(capability_id="fs.read")],
        path_grants=[PathGrant(capability_id="fs.read", path_prefix="/foo/bar")],
    )

    assert authority.allows("fs.read", path="/foo/bar").decision == "allowed"
    assert authority.allows("fs.read", path="/foo/bar/child.txt").decision == "allowed"

    decision = authority.allows("fs.read", path="/foo/barbaz")

    assert decision.decision == "blocked"
    assert decision.reason == "path_scope_blocked"


def test_network_and_credential_scope_must_match_requested_scope() -> None:
    authority = AuthorityContext(
        principal_id="principal",
        run_id="run-v210",
        goal_contract_id="goal-v210",
        capability_grants=[CapabilityGrant(capability_id="provider.local-smoke")],
        network_grants=[
            NetworkGrant(capability_id="provider.local-smoke", network_host="127.0.0.1"),
        ],
        credential_grants=[
            CredentialGrant(
                capability_id="provider.local-smoke",
                credential_scope="credential.local-smoke",
            ),
        ],
    )

    assert (
        authority.allows(
            "provider.local-smoke",
            network_host="127.0.0.1",
            credential_scope="credential.local-smoke",
        ).decision
        == "allowed"
    )

    network_decision = authority.allows("provider.local-smoke", network_host="api.example.com")
    credential_decision = authority.allows(
        "provider.local-smoke",
        credential_scope="credential.production",
    )

    assert network_decision.decision == "blocked"
    assert network_decision.reason == "network_scope_blocked"
    assert credential_decision.decision == "blocked"
    assert credential_decision.reason == "credential_scope_blocked"
