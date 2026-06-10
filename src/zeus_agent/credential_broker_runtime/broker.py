from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Iterable, Literal, Optional

from zeus_agent.live_sealed_credential_runtime import LiveSealedCredential
from zeus_agent.security.credentials import CredentialScope, CredentialScopeUnsafeError
from zeus_agent.trust_loop_runtime import SQLiteEvidenceLedger, TrustDecision

from .vault import CredentialVault

_SECRET_PROOF_SCHEME: Final = "secret-proof://"

# Only an allowed decision opens the vault. ASK/DENY never release material —
# an approved ASK must be re-decided into an allowed outcome first.
_RELEASABLE: Final[frozenset[TrustDecision]] = frozenset(
    {TrustDecision.AUTO, TrustDecision.NOTIFY}
)


def parse_secret_proof_ref(ref: str) -> str:
    """``secret-proof://<scope>`` → validated scope label, fail-closed.

    The scope must be a safe label (never secret-like material); validation is
    delegated to ``CredentialScope.parse`` which raises on anything that looks
    like a raw key.
    """
    value = ref.strip()
    if not value.startswith(_SECRET_PROOF_SCHEME):
        raise ValueError("malformed_secret_proof_ref")
    return CredentialScope.parse(value[len(_SECRET_PROOF_SCHEME):]).label


@dataclass(frozen=True)
class BrokerRelease:
    decision: Literal["released", "blocked"]
    reason: str
    credential: Optional[LiveSealedCredential] = None
    evidence_record_id: Optional[str] = None


class CredentialBrokerService:
    """Sealed credential release at the egress point only.

    The agent plans with ``secret-proof://`` refs and never holds raw keys.
    At the moment of egress the broker exchanges (allowed decision, capability,
    host) for a sealed credential, appends a release receipt linked to the
    decision receipt, and hands the sealed value to the transport.
    """

    def __init__(self, vault: CredentialVault, ledger: SQLiteEvidenceLedger) -> None:
        self._vault = vault
        self._ledger = ledger

    def release(
        self,
        *,
        ref: str,
        run_id: str,
        capability_id: str,
        network_host: str,
        approved_hosts: Iterable[str],
        trust_decision: TrustDecision,
        decision_record_id: Optional[str] = None,
    ) -> BrokerRelease:
        try:
            scope_label = parse_secret_proof_ref(ref)
        except CredentialScopeUnsafeError:
            return self._blocked(run_id, capability_id, network_host, "secret_like_ref")
        except ValueError as exc:
            return self._blocked(run_id, capability_id, network_host, str(exc))
        if trust_decision not in _RELEASABLE:
            return self._blocked(run_id, capability_id, network_host, "decision_not_allowed")
        approved = {host.strip() for host in approved_hosts if host.strip()}
        if network_host not in approved:
            return self._blocked(run_id, capability_id, network_host, "host_not_approved")
        entry = self._vault.resolve(scope_label)
        if entry is None:
            return self._blocked(run_id, capability_id, network_host, "credential_unavailable")
        # The ledger redactor treats any "secret*" marker as material, so the
        # receipt carries the bare scope label rather than the scheme-prefixed ref.
        event = self._ledger.append(
            kind="credential_release",
            run_id=run_id,
            payload={
                "scope_label": scope_label,
                "capability_id": capability_id,
                "network_host": network_host,
                "material_released": True,
                "caused_by": [] if decision_record_id is None else [decision_record_id],
            },
        )
        credential = LiveSealedCredential(
            header_name=entry.header_name,
            header_value_ref=_SECRET_PROOF_SCHEME + scope_label,
            _header_value=entry.reveal(),
        )
        return BrokerRelease(
            decision="released",
            reason="sealed_release",
            credential=credential,
            evidence_record_id=event.record_id,
        )

    def _blocked(
        self,
        run_id: str,
        capability_id: str,
        network_host: str,
        reason: str,
    ) -> BrokerRelease:
        event = self._ledger.append(
            kind="credential_release",
            run_id=run_id,
            payload={
                "capability_id": capability_id,
                "network_host": network_host,
                "material_released": False,
                "blocked_reason": reason,
            },
        )
        return BrokerRelease(decision="blocked", reason=reason, evidence_record_id=event.record_id)
