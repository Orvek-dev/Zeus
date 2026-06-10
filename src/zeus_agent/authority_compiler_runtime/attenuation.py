from __future__ import annotations

from typing import Sequence

from zeus_agent.kernel.authority import (
    AuthorityContext,
    CapabilityGrant,
    CredentialGrant,
    NetworkGrant,
    PathGrant,
)

from .models import AuthorityEnvelope


def authority_context_from(envelope: AuthorityEnvelope, *, run_id: str) -> AuthorityContext:
    """Project an envelope into the kernel's enforcement context."""
    capability_grants = [
        CapabilityGrant(capability_id=grant.capability_id) for grant in envelope.granted
    ]
    path_grants = [
        PathGrant(capability_id=grant.capability_id, path_prefix=path)
        for grant in envelope.granted
        for path in grant.path_scopes
    ]
    network_grants = [
        NetworkGrant(capability_id=grant.capability_id, network_host=host)
        for grant in envelope.granted
        for host in grant.network_hosts
    ]
    credential_grants = [
        CredentialGrant(capability_id=grant.capability_id, credential_scope=scope)
        for grant in envelope.granted
        for scope in grant.credential_scopes
    ]
    return AuthorityContext(
        principal_id=envelope.principal_id,
        run_id=run_id,
        goal_contract_id=envelope.objective_id,
        capability_grants=capability_grants,
        path_grants=path_grants,
        network_grants=network_grants,
        credential_grants=credential_grants,
    )


def derive_child_authority(
    envelope: AuthorityEnvelope,
    *,
    run_id: str,
    child_principal_id: str,
    requested_capabilities: Sequence[str],
) -> AuthorityContext:
    """Attenuate the envelope for a subagent.

    Anything outside the parent envelope raises (``derive_for_child`` is the
    kernel's existing fail-closed primitive) — a child can only ever hold a
    subset of what the objective earned.
    """
    parent = authority_context_from(envelope, run_id=run_id)
    return parent.derive_for_child(child_principal_id, requested_capabilities)
